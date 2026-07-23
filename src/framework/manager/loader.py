import os, sys, inspect, json, uuid, ast, types, asyncio, signal
from typing import Any, Type, Optional, Iterator
from graphlib import TopologicalSorter
from collections import defaultdict
from pathlib import Path
from jinja2 import Environment, BaseLoader
import tomli

MANAGER, ADAPTER = "manager", "adapter"

class Handle:
    def __init__(self, obj=None):
        # Usiamo un dizionario interno dedicato per lo stato dell'Handle
        super().__setattr__('_state', {})
        super().__setattr__('obj', None)
        if obj is not None:
            self.swap(obj)

    def swap(self, obj):
        # Salva il nuovo oggetto
        super().__setattr__('obj', obj)
        if obj is not None:
            # Sincronizza lo stato salvato finora nell'Handle dentro il nuovo obj
            for key, value in self._state.items():
                setattr(obj, key, value)

    def __getattr__(self, name):
        if name in ('obj', '_state'):
            return super().__getattribute__(name)
        return getattr(self.obj, name)

    def __setattr__(self, name, value):
        if name in ('obj', '_state'):
            super().__setattr__(name, value)
        else:
            # 1. Salva lo stato nell'Handle per non perderlo
            self._state[name] = value
            # 2. Aggiorna anche l'oggetto corrente (se esiste)
            if self.obj is not None:
                setattr(self.obj, name, value)

    def __repr__(self):
        if self.obj is None:
            return "<Handle object (empty)>"
        return str(self.obj).replace('.Manager', '.Manager.Handle')

class Framework:
    """
    Framework kernel.

    Responsabilità:
    - caricare moduli
    - caricare core
    - registrare componenti
    - risolvere ordine dipendenze

    NON crea istanze.
    NON gestisce DI.
    NON gestisce lifecycle.
    """

    def __init__(self):

        # nome componente -> descriptor
        self.components: dict[str, dict] = {}

        self.errors = []


    # =====================================================
    # Namespace
    # =====================================================

    def _pkg(self, name):

        if not name:
            return None

        if name in sys.modules:
            return sys.modules[name]


        pkg = types.ModuleType(name)

        pkg.__path__ = []

        pkg.__package__ = (
            name.rpartition(".")[0]
        )


        sys.modules[name] = pkg


        if "." in name:

            parent, child = name.rsplit(".",1)

            setattr(
                self._pkg(parent),
                child,
                pkg
            )


        return pkg



    # =====================================================
    # Python loader
    # =====================================================

    async def load_module(
        self,
        name,
        path,
        extra=None,
        force=False
    ):


        if name in sys.modules and not force:
            return sys.modules[name]


        self._pkg(
            name.rpartition(".")[0]
        )


        module = types.ModuleType(name)

        module.__file__ = path


        if extra:
            module.__dict__.update(extra)


        sys.modules[name] = module


        if "." in name:

            pkg, short = name.rsplit(".",1)

            setattr(
                self._pkg(pkg),
                short,
                module
            )


        try:

            code = Path(path).read_bytes()

            exec(
                compile(
                    code,
                    path,
                    "exec"
                ),
                module.__dict__
            )


        except Exception as e:

            sys.modules.pop(
                name,
                None
            )

            raise RuntimeError(
                f"Errore caricamento {name}: {e}"
            )


        print(f"[+] {name}")

        return module



    # =====================================================
    # Core bootstrap
    # =====================================================

    async def load_core(
        self,
        services,
        ports,
        extra_by_name=None
    ):


        extra_by_name = (
            extra_by_name or {}
        )


        modules = {
            **services,
            **ports
        }


        graph = {}

        pending = {}



        for name,path in modules.items():

            namespace = (
                "framework.service."
                + name
                if name in services
                else
                "framework.port."
                + name
            )


            code = Path(path).read_text()


            pending[name] = (
                namespace,
                path
            )


            graph[name] = {

                x.split(".")[-1]

                for x in self.imports(code)

            } & modules.keys()



        for name in TopologicalSorter(graph).static_order():


            if name not in pending:
                continue


            namespace,path = pending[name]


            await self.load_module(
                namespace,
                path,
                extra_by_name.get(name)
            )

            print(
                f"[✓] Core {namespace}"
            )



    # =====================================================
    # Discovery
    # =====================================================

    async def discover(
        self,
        name,
        path,
        kind,
        config=None,
        interface=None
    ):


        if not os.path.isfile(path):

            self.errors.append(
                f"File mancante {path}"
            )

            return None



        module = await self.load_module(
            name,
            path
        )


        expected = (
            "Manager"
            if kind == MANAGER
            else
            "Adapter"
        )


        cls = getattr(
            module,
            expected,
            None
        )


        if cls is None:

            self.errors.append(
                f"{expected} mancante in {name}"
            )

            return None



        descriptor = {

            "name": name,

            "cls": cls,

            "kind": kind,

            "interface": interface,

            "config": config or {},

            "path": path,

            "dependencies":
                self.dependencies(cls),

            "port_lists": {}

        }


        self.components[name] = descriptor


        print(
            f"[~] {kind}: {name}"
        )


        return descriptor



    # =====================================================
    # Registry
    # =====================================================

    def managers(self):

        return iter(
            [
                x
                for x in self.components.values()
                if x["kind"] == MANAGER
            ]
        )

    def adapters(self):

        return iter(
            [
                x
                for x in self.components.values()
                if x["kind"] == ADAPTER
            ]
        )



    # =====================================================
    # Dependency graph
    # =====================================================

    def build_order(self, kind):

        items = {
            x["name"]: x
            for x in self.components.values()
            if x["kind"] == kind
        }

        graph = {}

        for name, item in items.items():

            deps = set()

            for dep in item["dependencies"].values():

                module = getattr(
                    dep,
                    "__module__",
                    ""
                )

                dep_name = module.split(".")[-1]


                for other_name in items:

                    if other_name.endswith(dep_name):
                        deps.add(other_name)


            graph[name] = deps


        order = list(
            TopologicalSorter(graph).static_order()
        )


        return [
            items[name]
            for name in order
        ]
    # =====================================================
    # Reflection
    # =====================================================

    @staticmethod
    def dependencies(cls):

        return {

            name:p.annotation

            for name,p in
            inspect.signature(
                cls.__init__
            ).parameters.items()

            if name!="self"
            and p.annotation
            is not inspect.Parameter.empty

        }



    @staticmethod
    def imports(code):

        try:
            tree=ast.parse(code)
        except:
            return []


        result=set()


        for n in ast.walk(tree):

            if isinstance(n,ast.Import):

                for x in n.names:
                    result.add(x.name)


            elif isinstance(n,ast.ImportFrom):

                if n.module:
                    result.add(n.module)


        return list(result)



    @staticmethod
    def is_port_list(annotation):

        return (
            getattr(
                annotation,
                "__origin__",
                None
            )
            is list
        )


    # =====================================================
    # Validation
    # =====================================================

    def check(self):

        if self.errors:

            raise RuntimeError(
                "\n".join(self.errors)
            )

class Application:
    """Manager del Ciclo di Vita Globale dell'App."""

    def __init__(self, container, loader, managers: list, session=None):
        self._c = container
        self._loader = loader
        self._managers = managers
        self._stop_event = asyncio.Event()
        self._running_tasks: list = []
        self._session = session
        self._reload_lock = asyncio.Lock()

    async def _message_consumer_worker(self):
        try:
            while not self._stop_event.is_set():
                messenger = self._loader.get_managers().get('messenger')
                message = await messenger.read(self._session, domain="event")
                current_managers = self._loader.get_managers()
                for name, manager in list(current_managers.items()):
                    print(manager)
                    if hasattr(manager, 'reload'):
                        try:
                            await manager.reload(self._session, message)
                        except Exception as e:
                            print(f"[!] Errore durante il reload in {name}: {e}")
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

from collections import defaultdict
from typing import Type, Any, Union

class Container:
    """Singleton manager, istanze multiple adapter, porte collegate agli adapter."""

    def __init__(self):
        self._instances: dict = {}
        self._ports: dict = defaultdict(list)

    def _match(self, target: Union[Type, str], candidate_cls: Type) -> bool:
        """Verifica se una chiave o classe corrisponde a un target (classe o stringa parziale)."""
        if isinstance(target, str):
            search_str = target.lower()
            class_name = getattr(candidate_cls, '__name__', str(candidate_cls)).lower()
            module_name = getattr(candidate_cls, '__module__', '').lower()
            full_path = f"{module_name}.{class_name}"
            return search_str in class_name or search_str in full_path
        return candidate_cls is target or target == candidate_cls

    def put(self, cls: Type, obj: Any, singleton=True):
        if singleton:
            self._instances[cls] = [obj]
        else:
            self._instances.setdefault(cls, []).append(obj)

    def get(self, cls: Union[Type, str]):
        # 1. Cerca per corrispondenza (classe o stringa) tra le istanze registrate
        for k, val in self._instances.items():
            if self._match(cls, k) and val:
                return val[-1]

        # 2. Fallback sul nome del modulo se cls è una classe
        mod_name = getattr(cls, '__module__', None) if not isinstance(cls, str) else None
        if mod_name:
            for k, val in self._instances.items():
                if getattr(k, '__module__', None) == mod_name and val:
                    return val[-1]
        return None

    def remove(self, cls: Union[Type, str]):
        keys_to_pop = [
            k for k in self._instances 
            if self._match(cls, k) or (not isinstance(cls, str) and getattr(cls, '__module__', None) == getattr(k, '__module__', None))
        ]
        for k in keys_to_pop:
            self._instances.pop(k, None)

        mod_name = getattr(cls, '__module__', None) if not isinstance(cls, str) else None
        for iface, objs in list(self._ports.items()):
            self._ports[iface] = [
                o for o in objs 
                if not (self._match(cls, o.__class__) or (mod_name and getattr(o.__class__, '__module__', None) == mod_name))
            ]

    def add_port(self, iface: Union[Type, str], obj: Any):
        self._ports[iface].append(obj)

    def get_port(self, iface: Union[Type, str]):
        results = []
        
        # Se passi una stringa (es. "persistence", "network", ecc.)
        if isinstance(iface, str):
            for k, objs in self._ports.items():
                # Se la chiave è una stringa diretta o una classe/oggetto
                if isinstance(k, str):
                    if iface.lower() in k.lower():
                        results.extend(objs)
                else:
                    if self._match(iface, k):
                        results.extend(objs)
            return results
        
        # Altrimenti se passi la classe direttamente
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

    def _build_managers(self):

        instances = []

        for descriptor in self.framework.build_order(MANAGER):

            cls = descriptor["cls"]

            obj_in = cls(
                **self._kwargs(descriptor),
                **descriptor["config"]
            )

            obj = Handle(obj_in)

            self.container.put(
                cls,
                obj,
                singleton=True
            )

            instances.append(obj)

            print(
                f"[✓] Manager {cls.__module__}.{cls.__name__}"
            )


        return instances

    def _build_adapters(self, descriptors=None) -> None:
        """Se descriptors è None costruisce tutti gli adapter (bootstrap);
        altrimenti costruisce solo quelli passati (reload mirato)."""
        for descriptor in (descriptors if descriptors is not None else self.framework.adapters()):
            cls = descriptor['cls']
            obj_in = cls(**self._kwargs(descriptor), **descriptor['config'])
            obj = Handle(obj_in)
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

    
    async def reload(self, session, changed_path) -> bool:
        if changed_path.endswith('.py'):
            if '/infrastructure/' in changed_path:
                a = changed_path.split('/')
                for i,x in enumerate(a):
                    if x == "infrastructure":
                        index = i
                port = a[index+1]
                adapters = self.container.get_port(port)
                await self.framework.reload_module(changed_path)

            elif '/framework/manager/' in changed_path:
                print("manager",changed_path)
            else:
                print("module",changed_path)

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

        app = Application(self.container, self, instances, session)
        self.app = app
        return app