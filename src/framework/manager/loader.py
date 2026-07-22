import os, sys, inspect, json, uuid, ast, types, asyncio, signal
from typing import Any, Type, Optional, Iterator
from graphlib import TopologicalSorter
from collections import defaultdict
from pathlib import Path
from jinja2 import Environment, BaseLoader
import tomli

MANAGER, ADAPTER = "manager", "adapter"

class Framework:
    """Discovery, caricamento moduli, reflection e registro dei componenti (dict semplici)."""

    def __init__(self):
        self.components: list = []
        self.errors: list = []

    def _pkg(self, name: str) -> types.ModuleType:
        """Crea i package intermedi framework.x.y (non esistono su disco come veri package)."""
        if not name or name in sys.modules:
            return sys.modules.get(name)
        pkg = types.ModuleType(name)
        pkg.__path__ = []
        pkg.__package__ = name.rpartition('.')[0]
        sys.modules[name] = pkg
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            setattr(self._pkg(parent), child, pkg)
        return pkg

    async def load_module(self, name: str, path: str, extra: dict = None, force: bool = False) -> types.ModuleType:
        """
        Carica ed esegue un file come modulo. Usa compile()+exec() diretti invece di
        SourceFileLoader: quest'ultimo scrive/legge bytecode cache in __pycache__ basata
        su mtime, e su riscritture ravvicinate (hot reload) può riusare bytecode STALE
        anche dopo aver modificato il file. compile() legge sempre il contenuto attuale.
        """
        if name in sys.modules and not force:
            return sys.modules[name]

        self._pkg(name.rpartition('.')[0])

        mod = types.ModuleType(name)
        mod.__file__ = path
        if extra:
            mod.__dict__.update(extra)

        sys.modules[name] = mod
        if '.' in name:
            pkg, short = name.rsplit('.', 1)
            setattr(self._pkg(pkg), short, mod)

        try:
            code = open(path, 'rb').read()
            exec(compile(code, path, 'exec'), mod.__dict__)
        except Exception as e:
            del sys.modules[name]
            raise RuntimeError(f"'{name}': {e}") from e

        print(f"[+] {name}")
        return mod

    async def load_core(self, services: dict, ports: dict, extra_by_name: dict = None) -> None:
        """Carica service/port del core in ordine topologico sui loro import reciproci."""
        extra_by_name = extra_by_name or {}
        all_mods = services | ports
        codes, deps = {}, {}
        for short, path in all_mods.items():
            ns = f"framework.{'service' if short in services else 'port'}.{short}"
            if ns in sys.modules:
                continue
            code = open(path, 'rb').read().decode()
            codes[short] = (path, ns)
            deps[short] = {n.split('.')[-1] for n in self.imports(code)} & all_mods.keys()
        for name in TopologicalSorter(deps).static_order():
            if name not in codes:
                continue
            path, ns = codes[name]
            await self.load_module(ns, path, extra_by_name.get(name))

    @staticmethod
    def imports(code: str) -> list:
        try:
            tree = ast.parse(code)
        except Exception:
            return []
        seen = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names: seen[a.name] = None
            elif isinstance(n, ast.ImportFrom) and n.module:
                seen[n.module] = None
        return list(seen)

    @staticmethod
    def dependencies(cls: Type) -> dict:
        """Nome parametro -> tipo, dalle annotazioni del costruttore (escluso self)."""
        return {
            name: p.annotation
            for name, p in inspect.signature(cls.__init__).parameters.items()
            if name != 'self' and p.annotation is not inspect.Parameter.empty
        }

    @staticmethod
    def is_port_list(ann: Any) -> bool:
        return (hasattr(ann, '__origin__') and ann.__origin__ is list
                and bool(getattr(ann, '__args__', None)))

    def file_dependencies(self, file_path: str, root: str = "src") -> list:
        """
        Path reali su disco dei moduli importati da file_path (se esistono sotto root),
        più file_path stesso. A differenza di 'imports' (usato da reload per il nome),
        qui si risolve fino al file fisico: utile per capire quali sorgenti tocca un file
        anche se non sono (ancora) componenti scoperti dal Framework.
        """
        try:
            tree = ast.parse(Path(file_path).read_text(encoding="utf-8"))
        except Exception:
            return []

        deps = {file_path}

        def add(path: Path):
            if path.exists() and path.is_file():
                deps.add(str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add(Path(root, *alias.name.split(".")).with_suffix(".py"))
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                base = Path(root, *node.module.split("."))
                module_file = base.with_suffix(".py")
                if module_file.exists():
                    add(module_file)
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = (base / alias.name).with_suffix(".py")
                    if candidate.exists():
                        add(candidate)

        return sorted(deps)

    async def discover(self, name: str, path: str, kind: str, config: dict, interface: Type = None) -> Optional[dict]:
        """Carica un modulo e ne registra il descriptor (dict). Errori accumulati, non persi."""
        if not os.path.isfile(path):
            self.errors.append(f"modulo non trovato: '{path}' (atteso per '{name}')")
            return None

        class_name = 'Manager' if kind == MANAGER else 'Adapter'
        mod = await self.load_module(name, path)
        cls = getattr(mod, class_name, None)
        if cls is None:
            self.errors.append(f"classe '{class_name}' non trovata in '{name}' ({path})")
            return None

        descriptor = {
            'cls': cls, 'kind': kind, 'interface': interface, 'path': path,
            'dependencies': self.dependencies(cls), 'config': config, 'port_lists': {},
            # nomi (ultimo segmento) dei moduli importati dal file sorgente: usati per capire
            # quali adapter dipendono da un dato service/port quando quel file cambia.
            'imports': {n.split('.')[-1] for n in self.imports(open(path, 'rb').read().decode())},
        }
        self.components.append(descriptor)

        cfg_name = config.get('name') if isinstance(config, dict) else None
        print(f"[~] {class_name} '{cls.__name__}' scoperto" + (f" name='{cfg_name}'" if cfg_name else ""))
        return descriptor

    def remove(self, cls: Type) -> None:
        self.components = [c for c in self.components if c['cls'] is not cls]

    def check(self) -> None:
        if self.errors:
            details = "\n".join(f"  - {e}" for e in self.errors)
            raise RuntimeError(f"Discovery fallita per {len(self.errors)} componente/i:\n{details}")

    def by_kind(self, kind: str) -> Iterator:
        return (c for c in self.components if c['kind'] == kind)

    def managers(self) -> Iterator:
        return self.by_kind(MANAGER)

    def adapters(self) -> Iterator:
        return self.by_kind(ADAPTER)

    def build_order(self, kind: str) -> list:
        """Ordine topologico delle classi di un kind, sulle sole dipendenze verso lo stesso kind."""
        descriptors = list(self.by_kind(kind))
        cls_set = {d['cls'] for d in descriptors}
        graph = {cls: set() for cls in cls_set}
        for d in descriptors:
            graph[d['cls']] |= {dep for dep in d['dependencies'].values()
                                 if not self.is_port_list(dep) and dep in cls_set}
        return [c for c in TopologicalSorter(graph).static_order() if c in cls_set]

class Application:
    """Manager del Ciclo di Vita Globale dell'App."""

    def __init__(self, container, loader, managers: list, session=None):
        self._c = container
        self._loader = loader
        self._managers = managers
        self._stop_event = asyncio.Event()
        self._running_tasks: list = []
        self._session = session

    async def _message_consumer_worker(self):
        messenger = self._loader.get_managers().get('messenger')
        if messenger is None:
            print("[!] Nessun messenger trovato nel container. Il worker di messaggistica non può partire.")
            exit(1)

        try:
            while not self._stop_event.is_set():
                message = await messenger.read(self._session, domain="event")
                ok = await self._loader.reload(message)
                print(f"[Worker] Reload eseguito per: {ok}")
        except asyncio.CancelledError:
            print("[*] Worker di messaggistica terminato.")

    async def start(self) -> None:
        print("[*] Avvio dei manager del framework...")
        self._running_tasks.append(asyncio.create_task(self._message_consumer_worker()))

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._stop_event.set)

        for manager in self._managers:
            if hasattr(manager, "start"):
                res = await manager.start(self._session)
                if res:
                    if isinstance(res, list):
                        for coro in res: self._running_tasks.append(asyncio.create_task(coro))
                    elif asyncio.iscoroutine(res) or inspect.isawaitable(res):
                        self._running_tasks.append(asyncio.create_task(res))

        print("[+] Framework completamente attivo. In ascolto...")
        await self._stop_event.wait()

    async def stop(self) -> None:
        print("\n[*] Spegnimento controllato dei servizi...")
        for manager in reversed(self._managers):
            if hasattr(manager, "stop"):
                await manager.stop(self._session)
        for task in self._running_tasks:
            if not task.done():
                task.cancel()
        print("[*] Framework spento correttamente.")

class Infrastructure:
    """TOML, JSON, Jinja, schemi, risorse."""

    def __init__(self):
        self.jinja_env = Environment(loader=BaseLoader())
        self.jinja_env.filters.setdefault('tojson', json.dumps)
        self.jinja_env.globals['uuid4'] = lambda: str(uuid.uuid4())

    async def load_schemes(self, directories: list) -> dict:
        raw = {}
        for d in directories:
            if not os.path.exists(d):
                continue
            for f in os.listdir(d):
                if not f.endswith('.json'):
                    continue
                try:
                    raw[f[:-5]] = json.load(open(os.path.join(d, f), encoding='utf-8'))
                except json.JSONDecodeError as e:
                    print(f"[!] JSON {f}: {e}")

        cache = {}

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
                        g = self.jinja_env.globals.get(ref); return g() if callable(g) else g
                    return self.jinja_env.from_string(v).render(**{**self.jinja_env.globals, **raw, **cache})
                return v

            cache[name] = _r(obj); return cache[name]

        final = {name: resolve(name) for name in raw}
        print(f"[+] Schemi: {', '.join(sorted(final))}" if final else "[!] Nessuno schema")
        return final

    async def resource(self, path) -> str:
        if str(path).startswith('application/'):
            path = 'src/' + path
        return open(path, 'rb').read().decode()

class Container:
    """Singleton manager, istanze multiple adapter, porte collegate agli adapter."""

    def __init__(self):
        self._instances: dict = {}
        self._ports: dict = defaultdict(list)

    def put(self, cls: Type, obj: Any, singleton=True):
        if singleton:
            self._instances[cls] = [obj]
        else:
            self._instances.setdefault(cls, []).append(obj)

    def get(self, cls: Type):
        items = self._instances.get(cls)
        return items[-1] if items else None

    def remove(self, cls: Type):
        self._instances.pop(cls, None)
        for iface, objs in self._ports.items():
            self._ports[iface] = [o for o in objs if not isinstance(o, cls)]

    def add_port(self, iface: Type, obj: Any):
        self._ports[iface].append(obj)

    def get_port(self, iface: Type):
        return list(self._ports.get(iface, []))

class Loader:
    """Orchestratore: Framework per discovery/reflection, Infrastructure per I/O, Container per la DI."""

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
        'network':      'src/framework/port/network.py',
    }
    managers = {
        'defender':      'src/framework/manager/defender.py',
        'messenger':     'src/framework/manager/messenger.py',
        'presenter':     'src/framework/manager/presenter.py',
        'storekeeper':   'src/framework/manager/storekeeper.py',
        'orchestrator':  'src/framework/manager/orchestrator.py',
        'networker':     'src/framework/manager/networker.py',
    }

    def __init__(self):
        self.framework = Framework()
        self.infra = Infrastructure()
        self.container = Container()
        self.container.put(Loader, self)
        sys.modules['framework.loader'] = sys.modules[__name__]
        self.current_config: dict = {}

    def _port_interface(self, port_key: str) -> Optional[Type]:
        port_mod = sys.modules.get(f"framework.port.{port_key}")
        return getattr(port_mod, "Port", None) if port_mod else None

    async def _discover_adapters(self, config: dict) -> None:
        for port_key in self.ports:
            interface = self._port_interface(port_key)
            for adapter_name, adapter_config in config.get(port_key, {}).items():
                configs = adapter_config if isinstance(adapter_config, list) else [adapter_config]
                ns = f"framework.adapter.{port_key}.{adapter_name}"
                path = f"src/infrastructure/{port_key}/{adapter_name}.py"
                for cfg in configs:
                    await self.framework.discover(ns, path, ADAPTER, cfg, interface=interface)

    def _kwargs(self, descriptor: dict) -> dict:
        kwargs = {}
        for pname, ann in descriptor['dependencies'].items():
            if self.framework.is_port_list(ann):
                iface = ann.__args__[0]
                if descriptor['kind'] == MANAGER:
                    port_list: list = []
                    descriptor['port_lists'][pname] = (iface, port_list)
                    kwargs[pname] = port_list
                else:
                    kwargs[pname] = self.container.get_port(iface)
            else:
                dep = self.container.get(ann)
                if dep is None:
                    raise RuntimeError(f"{descriptor['cls'].__name__}: dipendenza {ann} mancante")
                kwargs[pname] = dep
        return kwargs

    def _build_managers(self, descriptors=None) -> list:
        """Se descriptors è None costruisce tutti i manager, nell'ordine topologico (bootstrap);
        altrimenti solo quelli passati, comunque rispettando l'ordine topologico globale (reload)."""
        wanted = {d['cls'] for d in descriptors} if descriptors is not None else None
        instances = []
        for cls in self.framework.build_order(MANAGER):
            if wanted is not None and cls not in wanted:
                continue
            descriptor = next(d for d in self.framework.managers() if d['cls'] is cls)
            obj = cls(**self._kwargs(descriptor), **descriptor['config'])
            self.container.put(cls, obj, singleton=True)
            instances.append(obj)
            print(f"[✓] Manager {cls.__name__}")
        return instances

    def _build_adapters(self, descriptors=None) -> None:
        """Se descriptors è None costruisce tutti gli adapter (bootstrap);
        altrimenti costruisce solo quelli passati (reload mirato)."""
        for descriptor in (descriptors if descriptors is not None else self.framework.adapters()):
            cls = descriptor['cls']
            obj = cls(**self._kwargs(descriptor), **descriptor['config'])
            self.container.put(cls, obj, singleton=False)
            if descriptor['interface']:
                self.container.add_port(descriptor['interface'], obj)
            name = descriptor['config'].get('name') if isinstance(descriptor['config'], dict) else None
            print(f"[✓] Adapter {cls.__name__}" + (f" name={name}" if name else ""))

    def _inject_ports(self) -> None:
        for descriptor in self.framework.managers():
            for pname, (iface, port_list) in descriptor['port_lists'].items():
                port_list[:] = self.container.get_port(iface)
                print(f"[~] {pname} <- {[x.__class__.__name__ for x in port_list]}")

    # ─────────────────────────────────────────
    # reload: un file cambia -> ricostruisci a catena chi dipende da lui -> re-inietta
    # ─────────────────────────────────────────

    async def reload(self, changed_path: str) -> bool:
        """
        Ricarica changed_path e tutto quello collegato a catena, per qualsiasi tipo
        di file del framework:

        - schema (.json)                  -> ricarica gli schemi e il service 'scheme'
        - service/port core (.py)         -> ricarica quel modulo
        - manager o adapter già scoperto  -> ricostruisce quel componente

        In ogni caso, chiunque importi (testualmente) il nome del file appena
        ricaricato viene a sua volta ricaricato e ricostruito, a catena
        (un manager che importa un altro manager, un adapter che importa un port, ecc.),
        finché non ci sono più nuovi componenti da aggiungere. Alla fine le liste
        di Port vengono re-iniettate nei manager (i "servizi" wired via TOML).
        """
        changed_path = str(changed_path)
        seed_names: set = set()
        to_reload: list = []

        if changed_path.endswith('.json'):
            # schema: non ha un descriptor proprio, ricarica tutti gli schemi e il
            # service 'scheme' che li espone (extra iniettato al momento del load)
            schemes = await self.load_schemes(["src/framework/scheme", "src/application/model"])
            sys.modules.pop("framework.service.scheme", None)
            await self.framework.load_module(
                "framework.service.scheme", self.services['scheme'], force=True,
                extra={"schemes": schemes, "jinja_env": self.infra.jinja_env},
            )
            seed_names = {'scheme'}

        elif changed_path in (self.services | self.ports).values():
            core = self.services | self.ports
            name = next(k for k, p in core.items() if p == changed_path)
            kind_dir = 'service' if changed_path in self.services.values() else 'port'
            sys.modules.pop(f"framework.{kind_dir}.{name}", None)
            await self.framework.load_module(f"framework.{kind_dir}.{name}", changed_path, force=True)
            seed_names = {name}

        else:
            target = next((d for d in self.framework.components if d['path'] == changed_path), None)
            if target is None:
                print(f"[reload] file non riconosciuto: {changed_path}")
                return False
            to_reload = [target]
            seed_names = {Path(changed_path).stem}

        # chiusura transitiva: chi importa (testualmente) uno dei nomi noti va
        # ricaricato, e il suo nome si aggiunge a quelli da cercare (effetto a catena)
        known = {d['cls'] for d in to_reload}
        frontier = seed_names
        while frontier:
            found = [d for d in self.framework.components if d['cls'] not in known and frontier & d['imports']]
            if not found:
                break
            to_reload += found
            known |= {d['cls'] for d in found}
            frontier = {Path(d['path']).stem for d in found}

        if not to_reload:
            print(f"[reload] nessun componente collegato a '{changed_path}'")
            return False

        rebuilt = []
        for d in to_reload:
            self.container.remove(d['cls'])
            self.framework.remove(d['cls'])
            sys.modules.pop(d['cls'].__module__, None)
            new_d = await self.framework.discover(d['cls'].__module__, d['path'], d['kind'], d['config'], d['interface'])
            if new_d:
                rebuilt.append(new_d)

        self._build_managers([d for d in rebuilt if d['kind'] == MANAGER])
        self._build_adapters([d for d in rebuilt if d['kind'] == ADAPTER])
        self._inject_ports()

        print(f"[reload] ricostruiti: {[d['cls'].__name__ for d in rebuilt]}")
        return True

    async def reload_resource(self, message) -> bool:
        """Messaggio atteso: {'type': 'file_changed', 'path': '...'}"""
        if not isinstance(message, dict) or message.get("type") != "file_changed":
            return False
        path = message.get("path")
        return await self.reload(path) if path else False

    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────

    async def load_schemes(self, directories: list) -> dict:
        return await self.infra.load_schemes(directories)

    async def resource(self, path) -> str:
        return await self.infra.resource(path)

    def file_dependencies(self, file_path: str, root: str = "src") -> list:
        return self.framework.file_dependencies(file_path, root)

    def get_managers(self) -> dict:
        result = {"loader": self}
        for descriptor in self.framework.managers():
            obj = self.container.get(descriptor['cls'])
            if obj:
                result[descriptor['cls'].__module__.split(".")[-1]] = obj
        return result

    async def bootstrap(self, config_toml_path: str) -> Application:
        schemes = await self.load_schemes(["src/framework/scheme", "src/application/model"])

        await self.framework.load_core(
            self.services, self.ports,
            extra_by_name={"scheme": {"schemes": schemes, "jinja_env": self.infra.jinja_env}},
        )

        config = tomli.loads(open(config_toml_path, "rb").read().decode())
        self.current_config = config

        print("\n[*] Discovery...")
        for short, path in self.managers.items():
            await self.framework.discover(f"framework.manager.{short}", path, MANAGER, config.get("manager", {}).get(short, {}))
        await self._discover_adapters(config)
        self.framework.check()

        print("\n[*] Build...")
        instances = self._build_managers()
        self._build_adapters()
        self._inject_ports()

        entry = self.container.get(next(self.framework.managers())['cls'])
        await entry.start()
        session = await entry.session_create()
        print(f"[*] Sessione creata: {session}")

        return Application(self.container, self, instances, session)