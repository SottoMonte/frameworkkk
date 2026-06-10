import os, sys, inspect, json, uuid, ast, types
from typing import Any, Type
from graphlib import TopologicalSorter
from collections import defaultdict
from jinja2 import Environment, BaseLoader
import tomli


# ── Container ────────────────────────────────────────────────────────────────

class Container:
    """Dizionario di istanze già costruite + liste di port per interfaccia."""

    def __init__(self):
        self._singletons: dict[Type, Any]        = {}
        self._ports:      dict[Type, list]        = defaultdict(list)

    def put(self, cls: Type, obj: Any)            -> None: self._singletons[cls] = obj
    def get(self, cls: Type)                      -> Any:  return self._singletons.get(cls)
    def add_port(self, iface: Type, obj: Any)     -> None: self._ports[iface].append(obj)
    def get_port(self, iface: Type)               -> list: return list(self._ports.get(iface, []))


# ── Loader ───────────────────────────────────────────────────────────────────

class Loader:

    services = {
        'flow':     'src/framework/service/flow.py',
        'factory':  'src/framework/service/factory.py',
        'language': 'src/framework/service/language.py',
        'scheme':   'src/framework/service/scheme.py',
        'manage':   'src/framework/port/manage.py',
    }
    ports = {
        'message':      'src/framework/port/message.py',
        'presentation': 'src/framework/port/presentation.py',
        'persistence':  'src/framework/port/persistence.py',
    }
    managers = {
        'messenger':   'src/framework/manager/messenger.py',
        'storekeeper': 'src/framework/manager/storekeeper.py',
        'orchestrator': 'src/framework/manager/orchestrator.py',
    }

    def __init__(self):
        self.container = Container()
        self._managers: dict[Type, dict] = {}   # cls → {deps, config, _port_lists}
        self._adapters: dict[Type, dict] = {}   # cls → {deps, config, port_interface}

    # ── moduli ───────────────────────────────────────────────────────────────

    def _pkg(self, name: str) -> types.ModuleType:
        """Crea i package intermedi framework.x.y se non esistono ancora."""
        if name in sys.modules:
            return sys.modules[name]
        pkg = types.ModuleType(name)
        pkg.__path__ = []; pkg.__package__ = name.rpartition('.')[0]
        pkg.__spec__ = pkg.__loader__ = None
        sys.modules[name] = pkg
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            setattr(self._pkg(parent), child, pkg)
        return pkg

    async def _load(self, name: str, path: str, extra: dict = None) -> types.ModuleType:
        if name in sys.modules:
            return sys.modules[name]
        self._pkg(name.rpartition('.')[0])
        code = open(path, 'rb').read().decode()
        mod  = types.ModuleType(name)
        mod.__file__ = path; mod.__package__ = name.rpartition('.')[0]
        mod.__spec__ = mod.__loader__ = None
        sys.modules[name] = mod
        if '.' in name:
            pkg, short = name.rsplit('.', 1)
            setattr(self._pkg(pkg), short, mod)
        if extra:
            mod.__dict__.update(extra)
        try:
            exec(compile(code, path, 'exec'), mod.__dict__)
        except Exception as e:
            del sys.modules[name]; raise RuntimeError(f"'{name}': {e}") from e
        print(f"[+] {name}")
        return mod

    async def _load_framework(self):
        """Carica service + port in ordine topologico."""
        all_mods = self.services | self.ports
        codes, deps = {}, {}
        for short, path in all_mods.items():
            ns = f"framework.{'service' if short in self.services else 'port'}.{short}"
            if ns in sys.modules: continue
            code = open(path, 'rb').read().decode()
            codes[short] = (code, path, ns)
            imports = {n.split('.')[-1] for n in self._imports(code)}
            deps[short] = imports & all_mods.keys()
        for name in TopologicalSorter(deps).static_order():
            if name not in codes: continue
            code, path, ns = codes[name]
            extra = {'schemes': self._schemes} if ns == 'framework.service.scheme' else {}
            await self._load(ns, path, extra)

    @staticmethod
    def _imports(code: str) -> list[str]:
        try:    tree = ast.parse(code)
        except: return []
        seen = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names: seen[a.name] = None
            elif isinstance(n, ast.ImportFrom) and n.module:
                seen[n.module] = None
        return list(seen)

    @staticmethod
    def _deps(cls: Type) -> list[Type]:
        """Legge le annotazioni del costruttore (escluso self)."""
        return [
            p.annotation for name, p in inspect.signature(cls.__init__).parameters.items()
            if name != 'self' and p.annotation is not inspect.Parameter.empty
        ]

    @staticmethod
    def _is_port_list(ann: Any) -> bool:
        return (hasattr(ann, '__origin__') and ann.__origin__ is list
                and bool(getattr(ann, '__args__', None)))

    # ── discover ─────────────────────────────────────────────────────────────

    async def _discover(self, ns: str, path: str, config: dict,
                        port_key: str = None) -> None:
        """Carica un modulo e ne registra metadati senza istanziare nulla."""
        if not os.path.isfile(path):
            print(f"[!] Non trovato: {path}"); return

        is_manager  = port_key is None
        class_name  = 'Manager' if is_manager else 'Adapter'
        mod         = await self._load(ns, path)
        cls         = getattr(mod, class_name, None)
        if cls is None:
            print(f"[!] Classe '{class_name}' non trovata in '{ns}'"); return

        meta = {'deps': self._deps(cls), 'config': config}

        if is_manager:
            self._managers[cls] = meta
            print(f"[~] Manager '{cls.__name__}' scoperto")
        else:
            port_mod = sys.modules.get(f"framework.port.{port_key}")
            meta['port_interface'] = getattr(port_mod, 'Port', None) if port_mod else None
            self._adapters[cls] = meta
            print(f"[~] Adapter '{cls.__name__}' scoperto (port: {port_key})")

    # ── build ─────────────────────────────────────────────────────────────────

    def _kwargs(self, cls: Type, meta: dict, is_manager: bool) -> dict:
        """
        Costruisce kwargs per il costruttore di cls.
        Per i manager le list[Port] diventano liste vuote la cui referenza
        viene salvata in meta['_port_lists'] per inject_ports().
        Per gli adapter le list[Port] vengono risolte subito dal container.
        """
        kwargs = {}
        param_names = [
            n for n, p in inspect.signature(cls.__init__).parameters.items()
            if n != 'self' and p.annotation is not inspect.Parameter.empty
        ]
        for pname, ann in zip(param_names, meta['deps']):
            if self._is_port_list(ann):
                if is_manager:
                    port_list: list = []
                    meta.setdefault('_port_lists', {})[pname] = (ann.__args__[0], port_list)
                    kwargs[pname] = port_list
                else:
                    kwargs[pname] = self.container.get_port(ann.__args__[0])
            else:
                dep = self.container.get(ann)
                if dep is None:
                    raise RuntimeError(f"'{cls.__name__}': dipendenza '{ann}' non trovata.")
                kwargs[pname] = dep
        return kwargs

    def _build_managers(self) -> list[Any]:
        # ordine topologico solo sulle dipendenze manager→manager
        mgr_set = set(self._managers)
        graph   = {
            cls: {d for d in meta['deps'] if not self._is_port_list(d) and d in mgr_set}
            for cls, meta in self._managers.items()
        }
        order    = [c for c in TopologicalSorter(graph).static_order() if c in mgr_set]
        instances = []
        for cls in order:
            meta     = self._managers[cls]
            instance = cls(**self._kwargs(cls, meta, is_manager=True), **meta['config'])
            self.container.put(cls, instance)
            print(f"[✓] Manager '{cls.__name__}'")
            instances.append(instance)
        return instances

    def _build_adapters(self) -> None:
        for cls, meta in self._adapters.items():
            instance = cls(**self._kwargs(cls, meta, is_manager=False), **meta['config'])
            self.container.put(cls, instance)
            iface = meta['port_interface']
            if iface: self.container.add_port(iface, instance)
            print(f"[✓] Adapter '{cls.__name__}'" + (f" → {iface.__name__}" if iface else ""))

    def _inject_ports(self) -> None:
        """Popola le liste vuote dei manager con gli adapter ora costruiti."""
        for meta in self._managers.values():
            for pname, (iface, port_list) in meta.get('_port_lists', {}).items():
                adapters = self.container.get_port(iface)
                port_list.extend(adapters)
                print(f"[~] '{pname}' ← {[a.__class__.__name__ for a in adapters]}")

    # ── schemi ────────────────────────────────────────────────────────────────

    async def load_schemes(self, directories: list[str]) -> dict:
        raw: dict[str, Any] = {}
        for d in directories:
            if not os.path.exists(d): continue
            for f in os.listdir(d):
                if not f.endswith('.json'): continue
                try:
                    raw[f[:-5]] = json.load(open(os.path.join(d, f), encoding='utf-8'))
                except json.JSONDecodeError as e:
                    print(f"[!] JSON {f}: {e}")

        env = Environment(loader=BaseLoader())
        env.filters.setdefault('tojson', json.dumps)
        env.globals['uuid4'] = lambda: str(uuid.uuid4())
        cache: dict[str, Any] = {}

        def resolve(name: str) -> Any:
            if name in cache: return cache[name]
            obj = raw.get(name)
            if obj is None: return None
            cache[name] = {}

            def _r(v):
                if isinstance(v, dict):  return {k: _r(x) for k, x in v.items()}
                if isinstance(v, list):  return [_r(x) for x in v]
                if isinstance(v, str) and '{{' in v:
                    s = v.strip()
                    if s.startswith('{{') and s.endswith('}}') and '|' not in s:
                        ref = s[2:-2].strip()
                        if ref in raw: return resolve(ref)
                        g = env.globals.get(ref); return g() if callable(g) else g
                    return env.from_string(v).render(**{**env.globals, **raw, **cache})
                return v

            cache[name] = _r(obj); return cache[name]

        final = {name: resolve(name) for name in raw}
        print(f"[+] Schemi: {', '.join(sorted(final))}" if final else "[!] Nessuno schema")
        try:
            from cerberus import schema_registry
            for name, schema in final.items():
                try: schema_registry.add(name, schema)
                except Exception: pass
        except ImportError: pass
        return final

    # ── bootstrap ─────────────────────────────────────────────────────────────

    async def bootstrap(self, config_toml_path: str) -> Any:
        """
        1. discover  — carica file, legge firme, zero istanze
        2. managers  — costruisce in ordine topologico (list[Port] = [])
        3. adapters  — costruisce; trovano i manager pronti
        4. inject    — popola le liste vuote dei manager via mutazione
        """
        self._schemes = await self.load_schemes(
            ['src/framework/scheme', 'src/application/model'])
        await self._load_framework()

        config = tomli.loads(open(config_toml_path, 'rb').read().decode())

        print('\n[*] Discover...')
        for short, path in self.managers.items():
            await self._discover(f'framework.manager.{short}', path, {})

        for port_key in self.ports:
            for adapter_name, raw_cfg in config.get(port_key, {}).items():
                cfg  = raw_cfg[0] if isinstance(raw_cfg, list) else raw_cfg
                path = f'src/infrastructure/{port_key}/{adapter_name}.py'
                await self._discover(
                    f'framework.adapter.{port_key}.{adapter_name}', path, cfg, port_key)

        print('\n[*] Build...')
        instances = self._build_managers()
        self._build_adapters()
        self._inject_ports()

        return sys.modules['framework.service.factory'].Application(self.container, instances)