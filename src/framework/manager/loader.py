import os
import sys
import importlib.util
import inspect
import json
import uuid
import ast
from typing import Type, TypeVar, Any
import types
from graphlib import TopologicalSorter
from jinja2 import Environment, BaseLoader
import tomli
from collections import defaultdict

T = TypeVar('T')

_SENTINEL = object()   # marcatore "costruzione in corso" per rilevare cicli reali


# ─────────────────────────────────────────────
# CONTAINER  — dizionario di istanze già costruite + liste di port
# ─────────────────────────────────────────────

class ContainerWrapper:
    """
    Container minimalista senza dependency-injector providers.

    Scelta progettuale
    ------------------
    dependency-injector risolve i provider in modo ricorsivo sincrono e non
    tiene traccia degli oggetti "in costruzione".  Con il grafo:

        MessengerManager → list[MessagePort]
            ConsoleAdapter → StorekeeperManager → MessengerManager   ← ciclo

    qualsiasi combinazione di Singleton/Callable produce RecursionError.

    La soluzione è gestire noi la risoluzione con un dizionario di istanze
    già costruite (_instances).  Quando _resolve() incontra una classe che
    sta già costruendo (marcata _SENTINEL) solleva un errore chiaro invece
    di ricorrere all'infinito.

    I Port sono liste di istanze già costruite, non di provider.
    """

    def __init__(self):
        self._instances: dict[Type, Any] = {}   # cls → istanza già pronta
        self._ports: dict[Type, list[Any]] = defaultdict(list)  # iface → [istanze]

    # ── singleton ─────────────────────────────────────────────────────

    def put(self, cls: Type, instance: Any) -> None:
        """Registra un'istanza già costruita."""
        self._instances[cls] = instance

    def get(self, cls: Type[T]) -> T | None:
        return self._instances.get(cls)

    def has(self, cls: Type) -> bool:
        return cls in self._instances

    # ── port ──────────────────────────────────────────────────────────

    def add_port(self, interface: Type, instance: Any) -> None:
        self._ports[interface].append(instance)

    def get_port(self, interface: Type[T]) -> list[T]:
        return list(self._ports.get(interface, []))

    def has_port(self, interface: Type) -> bool:
        return bool(self._ports.get(interface))


# ─────────────────────────────────────────────
# RESOLVER  — costruisce il grafo nell'ordine corretto
# ─────────────────────────────────────────────

class Resolver:
    """
    Costruisce le istanze in ordine topologico gestendo due tipi di dipendenze:

    1. Dipendenza singola (cls):        risolve il singleton corrispondente.
    2. Lista di port (list[Interface]): restituisce tutte le istanze già
                                        registrate per quell'interfaccia.

    Il flag _building evita cicli reali (es. A → B → A) con un errore
    chiaro invece di una ricorsione infinita.

    Il trucco per il grafo Messenger → Console → Storekeeper → Messenger
    -----------------------------------------------------------------------
    Apparentemente ciclico, ma NON lo è se si separano le due fasi:

      FASE A — costruiamo i manager in ordine topologico e li mettiamo
               nel container.  In questa fase i Port sono ancora vuoti.

      FASE B — costruiamo gli adapter.  Ogni adapter riceve il manager
               già costruito nella fase A.

      FASE C — i manager che hanno list[Port] tra le dipendenze ricevono
               la lista DOPO che gli adapter sono stati costruiti.
               Questo richiede che i manager accettino la lista come
               argomento posticipato oppure che la si inietti dopo la
               costruzione tramite un attributo.

    Strategia adottata (più semplice e compatibile con i Manager esistenti)
    -----------------------------------------------------------------------
    Costruiamo i manager SENZA la lista di port (passiamo lista vuota []).
    Dopo aver costruito tutti gli adapter, aggiorniamo l'attributo del
    manager con la lista completa.  Il nome dell'attributo viene letto
    dalla firma del costruttore.
    """

    def __init__(
        self,
        container: ContainerWrapper,
        managers_meta: dict,   # cls → {deps, config, port_param}
        adapters_meta: dict,   # cls → {deps, config, port_interface}
    ):
        self.container     = container
        self.managers_meta = managers_meta
        self.adapters_meta = adapters_meta
        self._building: set[Type] = set()

    # ── fase A: manager ───────────────────────────────────────────────

    def build_managers(self) -> list[Any]:
        """
        Costruisce i manager in ordine topologico.
        Le dipendenze list[Port] vengono passate come [] e aggiornate dopo.
        """
        # costruiamo il grafo solo sulle dipendenze manager→manager
        mgr_deps: dict[Type, set[Type]] = {}
        for cls, meta in self.managers_meta.items():
            mgr_deps[cls] = {
                dep for dep in meta['deps']
                if not self._is_port_list(dep)
                and dep in self.managers_meta
            }

        try:
            order = [c for c in TopologicalSorter(mgr_deps).static_order()
                     if c in self.managers_meta]
        except Exception as e:
            raise RuntimeError(f"Dipendenza circolare tra manager: {e}") from e

        instances = []
        for cls in order:
            meta     = self.managers_meta[cls]
            instance = self._build_manager(cls, meta)
            self.container.put(cls, instance)
            print(f"[✓] Manager '{cls.__name__}' costruito")
            instances.append(instance)

        return instances

    def _build_manager(self, cls: Type, meta: dict) -> Any:
        kwargs: dict[str, Any] = {}
        sig = inspect.signature(cls.__init__)
        param_names = [
            p for p in sig.parameters if p != 'self'
            and sig.parameters[p].annotation is not inspect.Parameter.empty
        ]
        for pname, annotation in zip(param_names, meta['deps']):
            if self._is_port_list(annotation):
                # Creiamo la lista vuota e la salviamo nei metadati.
                # Poiché Python passa le liste per riferimento, il manager
                # internamente avrà un riferimento allo STESSO oggetto lista.
                # inject_ports() farà list.extend() su questo stesso oggetto
                # senza dover conoscere il nome dell'attributo interno.
                port_list: list = []
                meta.setdefault('_port_lists', {})[pname] = (annotation.__args__[0], port_list)
                kwargs[pname] = port_list
            else:
                dep = self.container.get(annotation)
                if dep is None:
                    raise RuntimeError(
                        f"Manager '{cls.__name__}': dipendenza '{annotation}' "
                        f"non ancora costruita."
                    )
                kwargs[pname] = dep
        return cls(**kwargs, **meta['config'])

    # ── fase B: adapter ───────────────────────────────────────────────

    def build_adapters(self) -> None:
        """
        Costruisce gli adapter nell'ordine di scoperta.
        Ogni adapter trova i manager già pronti nel container.
        """
        for cls, meta in self.adapters_meta.items():
            instance = self._build_adapter(cls, meta)
            self.container.put(cls, instance)
            iface = meta['port_interface']
            if iface is not None:
                self.container.add_port(iface, instance)
            print(f"[✓] Adapter '{cls.__name__}' costruito"
                  + (f" → Port '{iface.__name__}'" if iface else ""))

    def _build_adapter(self, cls: Type, meta: dict) -> Any:
        kwargs: dict[str, Any] = {}
        sig = inspect.signature(cls.__init__)
        param_names = [
            p for p in sig.parameters if p != 'self'
            and sig.parameters[p].annotation is not inspect.Parameter.empty
        ]
        for pname, annotation in zip(param_names, meta['deps']):
            if self._is_port_list(annotation):
                kwargs[pname] = self.container.get_port(annotation.__args__[0])
            else:
                dep = self.container.get(annotation)
                if dep is None:
                    raise RuntimeError(
                        f"Adapter '{cls.__name__}': dipendenza '{annotation}' "
                        f"non trovata nel container."
                    )
                kwargs[pname] = dep
        return cls(**kwargs, **meta['config'])

    # ── fase C: inject port lists nei manager ─────────────────────────

    def inject_ports(self) -> None:
        """
        Popola le liste di adapter nei manager tramite mutazione per riferimento.

        Durante _build_manager() ogni list[Port] è stata creata come lista vuota
        e salvata in meta['_port_lists'].  Il manager ha ricevuto quella stessa
        lista al costruttore (self.providers = messages, ecc.).
        Estendendo qui la lista originale, il manager vede automaticamente
        gli adapter senza che dobbiamo conoscere il nome dell'attributo interno.
        """
        for cls, meta in self.managers_meta.items():
            port_lists = meta.get('_port_lists', {})
            for pname, (iface, port_list) in port_lists.items():
                adapters = self.container.get_port(iface)
                port_list.extend(adapters)
                print(f"[~] '{cls.__name__}.{pname}' popolato "
                      f"con {len(adapters)} adapter: "
                      f"{[a.__class__.__name__ for a in adapters]}")

    # ── utilità ───────────────────────────────────────────────────────

    @staticmethod
    def _is_port_list(annotation: Any) -> bool:
        return (
            hasattr(annotation, "__origin__")
            and annotation.__origin__ is list
            and bool(getattr(annotation, "__args__", None))
        )


# ─────────────────────────────────────────────
# LOADER — discover → build → inject
# ─────────────────────────────────────────────

class Loader:

    services: dict[str, str] = {
        'flow':     'src/framework/service/flow.py',
        'factory':  'src/framework/service/factory.py',
        'language': 'src/framework/service/language.py',
        'scheme':   'src/framework/service/scheme.py',
        'manage':   'src/framework/port/manage.py',
    }

    ports: dict[str, str] = {
        'message':      'src/framework/port/message.py',
        'presentation': 'src/framework/port/presentation.py',
        'persistence':  'src/framework/port/persistence.py',
    }

    managers: dict[str, str] = {
        'messenger':   'src/framework/manager/messenger.py',
        'storekeeper': 'src/framework/manager/storekeeper.py',
    }

    def __init__(self):
        self.container = ContainerWrapper()
        self._discovered_managers: dict[Type, dict] = {}
        self._discovered_adapters: dict[Type, dict] = {}
        self._modules: dict[str, types.ModuleType]  = {}

    # ══════════════════════════════════════════════════════════════════
    # Utilità — moduli
    # ══════════════════════════════════════════════════════════════════

    def _ensure_package(self, name: str) -> types.ModuleType:
        if name in sys.modules:
            return sys.modules[name]
        pkg = types.ModuleType(name)
        pkg.__path__    = []
        pkg.__package__ = name.rpartition('.')[0]
        pkg.__spec__    = importlib.util.spec_from_loader(name, loader=None)
        pkg.__loader__  = None
        sys.modules[name] = pkg
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            setattr(self._ensure_package(parent), child, pkg)
        return pkg

    def _register_module(self, name: str, mod: types.ModuleType) -> None:
        sys.modules[name]     = mod
        self._modules[name]   = mod
        if '.' in name:
            pkg, short = name.rsplit('.', 1)
            setattr(self._ensure_package(pkg), short, mod)

    async def _read(self, path: str) -> str:
        with open(path, "rb") as f:
            return f.read().decode()

    async def _load_module(
        self, name: str, path: str, extra: dict | None = None
    ) -> types.ModuleType:
        if name in sys.modules:
            return sys.modules[name]
        if '.' in name:
            self._ensure_package(name.rpartition('.')[0])
        code = await self._read(path)
        mod             = types.ModuleType(name)
        mod.__file__    = path
        mod.__package__ = name.rpartition('.')[0]
        mod.__spec__    = importlib.util.spec_from_loader(name, loader=None)
        mod.__loader__  = None
        self._register_module(name, mod)
        if extra:
            mod.__dict__.update(extra)
        try:
            exec(compile(code, path, 'exec'), mod.__dict__)
        except Exception as e:
            del sys.modules[name]
            self._modules.pop(name, None)
            raise RuntimeError(f"Errore '{name}' da '{path}': {e}") from e
        print(f"[+] Modulo '{name}' caricato da '{path}'")
        return mod

    async def _extract_imports(self, code: str) -> list[str]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        seen: dict[str, None] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    seen[alias.name] = None
            elif isinstance(node, ast.ImportFrom) and node.module:
                seen[node.module] = None
        return list(seen)

    async def _load_framework_modules(self) -> None:
        all_mods = self.services | self.ports
        codes: dict[str, tuple] = {}
        deps:  dict[str, set]   = {}

        for short, path in all_mods.items():
            qualified = (
                f"framework.service.{short}" if short in self.services
                else f"framework.port.{short}"
            )
            if qualified in sys.modules:
                continue
            code             = await self._read(path)
            codes[short]     = (code, path, qualified)
            imports          = await self._extract_imports(code)
            normalized       = {i.split('.')[-1] for i in imports}
            deps[short]      = normalized & (self.services.keys() | self.ports.keys())

        for name in TopologicalSorter(deps).static_order():
            if name not in codes:
                continue
            code, path, qualified = codes[name]
            extra = {'schemes': self._schemes} if qualified == 'framework.service.scheme' else {}
            await self._load_module(qualified, path, extra)

    # ══════════════════════════════════════════════════════════════════
    # FASE 1 — DISCOVER
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _read_deps(cls: Type) -> list[Type]:
        sig = inspect.signature(cls.__init__)
        return [
            param.annotation
            for name, param in sig.parameters.items()
            if name != 'self' and param.annotation is not inspect.Parameter.empty
        ]

    async def _discover_manager(self, short: str, path: str, config: dict) -> None:
        mod = await self._load_module(f"framework.manager.{short}", path)
        cls = getattr(mod, 'Manager', None)
        if cls is None:
            print(f"[!] Manager non trovato in 'framework.manager.{short}'")
            return
        self._discovered_managers[cls] = {
            'deps':   self._read_deps(cls),
            'config': config,
        }
        print(f"[~] Manager '{cls.__name__}' scoperto")

    async def _discover_adapter(
        self, short: str, port_key: str, path: str, config: dict
    ) -> None:
        mod_name = f"framework.adapter.{port_key}.{short}"
        mod      = await self._load_module(mod_name, path)
        cls      = getattr(mod, 'Adapter', None)
        if cls is None:
            print(f"[!] Adapter non trovato in '{mod_name}'")
            return
        port_mod  = sys.modules.get(f"framework.port.{port_key}")
        iface     = getattr(port_mod, 'Port', None) if port_mod else None
        self._discovered_adapters[cls] = {
            'deps':           self._read_deps(cls),
            'config':         config,
            'port_interface': iface,
        }
        print(f"[~] Adapter '{cls.__name__}' scoperto (port: {port_key})")

    # ══════════════════════════════════════════════════════════════════
    # Schemi
    # ══════════════════════════════════════════════════════════════════

    async def load_schemes(self, directories: list[str]) -> dict:
        raw: dict[str, Any] = {}
        for directory in directories:
            if not os.path.exists(directory):
                continue
            for filename in os.listdir(directory):
                if not filename.endswith(".json"):
                    continue
                name = os.path.splitext(filename)[0]
                with open(os.path.join(directory, filename), encoding="utf-8") as f:
                    try:
                        raw[name] = json.load(f)
                    except json.JSONDecodeError as e:
                        print(f"[!] Errore JSON in {filename}: {e}")

        env = Environment(loader=BaseLoader())
        env.filters.setdefault('tojson', json.dumps)
        env.globals['uuid4'] = lambda: str(uuid.uuid4())
        cache: dict[str, Any] = {}

        def resolve(name: str) -> Any:
            if name in cache:
                return cache[name]
            obj = raw.get(name)
            if obj is None:
                return None
            cache[name] = {}

            def _r(v: Any) -> Any:
                if isinstance(v, dict):
                    return {k: _r(x) for k, x in v.items()}
                if isinstance(v, list):
                    return [_r(x) for x in v]
                if isinstance(v, str) and "{{" in v:
                    s = v.strip()
                    if s.startswith("{{") and s.endswith("}}") and "|" not in s:
                        ref = s[2:-2].strip()
                        if ref in raw:
                            return resolve(ref)
                        g = env.globals.get(ref)
                        return g() if callable(g) else g
                    ctx = {**env.globals, **raw, **{k: x for k, x in cache.items() if x}}
                    return env.from_string(v).render(**ctx)
                return v

            resolved     = _r(obj)
            cache[name]  = resolved
            return resolved

        final = {name: resolve(name) for name in raw}
        print(f"[+] Schemi caricati: {', '.join(sorted(final.keys()))}" if final
              else "[!] Nessuno schema caricato")
        try:
            from cerberus import schema_registry
            for name, schema in final.items():
                try:
                    schema_registry.add(name, schema)
                except Exception:
                    pass
        except ImportError:
            pass
        return final

    # ══════════════════════════════════════════════════════════════════
    # BOOTSTRAP
    # ══════════════════════════════════════════════════════════════════

    async def bootstrap(self, config_toml_path: str) -> Any:
        """
        Sequenza di boot in quattro passi netti:

        1. discover   — carica i moduli Python, legge le firme, zero istanze
        2. build mgr  — costruisce i manager in ordine topologico
                        (list[Port] inizialmente [])
        3. build adp  — costruisce gli adapter; ogni adapter trova i manager pronti
        4. inject     — inietta le liste di adapter nei manager che le richiedono
        """
        # prerequisiti
        self._schemes = await self.load_schemes(
            ["src/framework/scheme", "src/application/model"]
        )
        await self._load_framework_modules()

        raw_config  = await self._read(config_toml_path)
        config_data = tomli.loads(raw_config)

        # ── FASE 1: DISCOVER ──────────────────────────────────────────
        print("\n[*] Fase 1: Discovery...")

        for short, path in self.managers.items():
            await self._discover_manager(short, path, config={})

        for port_key in self.ports:
            if port_key not in config_data:
                continue
            for i, adapter_name in enumerate(config_data[port_key]):
                raw_cfg = config_data[port_key][adapter_name]
                cfg     = raw_cfg[i] if isinstance(raw_cfg, list) else raw_cfg
                path    = f"src/infrastructure/{port_key}/{adapter_name}.py"
                await self._discover_adapter(adapter_name, port_key, path, cfg)

        # ── FASI 2-4: BUILD + INJECT ──────────────────────────────────
        print("\n[*] Fase 2: Costruzione manager...")
        resolver = Resolver(
            self.container,
            self._discovered_managers,
            self._discovered_adapters,
        )
        manager_instances = resolver.build_managers()

        print("\n[*] Fase 3: Costruzione adapter...")
        resolver.build_adapters()

        print("\n[*] Fase 4: Iniezione port list nei manager...")
        resolver.inject_ports()

        factory = sys.modules['framework.service.factory']
        return factory.Application(self.container, manager_instances)