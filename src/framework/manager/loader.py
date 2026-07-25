import os, sys, inspect, json, uuid, ast, types, asyncio, signal
from typing import Any, Type, Optional, Iterator
from graphlib import TopologicalSorter
from collections import defaultdict
from pathlib import Path
from jinja2 import Environment, BaseLoader
import tomli
from dataclasses import dataclass, field

@dataclass
class Resource:
    name: str
    path: str
    module: any = None
    kind: str = None
    config: dict = field(
        default_factory=dict
    )
    extend: dict = field(
        default_factory=dict
    )

class Handle:
    def __init__(self, obj=None):
        # Usiamo un dizionario interno dedicato per lo stato dell'Handle
        super().__setattr__('_state', {})
        super().__setattr__('obj', None)
        if obj is not None:
            self.swap(obj)
        self.init = True

    def swap2(self, obj):
        # Salva il nuovo oggetto
        super().__setattr__('obj', obj)
        if obj is not None:
            # Sincronizza lo stato salvato finora nell'Handle dentro il nuovo obj
            for key, value in self._state.items():
                setattr(obj, key, value)

    def swap(self,obj):

        old = self.obj

        if old is not None and obj is not None:
            for key,value in old.__dict__.items():
                if key not in ("__dict__",):
                    setattr(obj,key,value)

        super().__setattr__('obj',obj)

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

class Reflection:
    """Utility di reflection sui moduli Python."""

    @staticmethod
    def imports(code: str) -> list[str]:
        try:
            tree = ast.parse(code)
        except Exception:
            return []

        result = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result.add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result.add(node.module)

        return list(result)

    @staticmethod
    def dependencies(cls):
        return {
            name: p.annotation
            for name, p in inspect.signature(cls.__init__).parameters.items()
            if name != "self"
            and p.annotation is not inspect.Parameter.empty
        }

    @staticmethod
    def is_port_list(annotation):
        return (
            getattr(annotation, "__origin__", None)
            is list
        )

    @staticmethod
    def file_dependencies(file_path: str, root="src"):

        try:
            tree = ast.parse(Path(file_path).read_text())
        except Exception:
            return []

        deps = {file_path}

        def add(path):
            if path.exists():
                deps.add(str(path))

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                for alias in node.names:
                    add(
                        Path(root, *alias.name.split(".")).with_suffix(".py")
                    )

            elif isinstance(node, ast.ImportFrom):

                if node.module is None:
                    continue

                base = Path(root, *node.module.split("."))

                module = base.with_suffix(".py")

                if module.exists():
                    add(module)
                    continue

                for alias in node.names:

                    if alias.name == "*":
                        continue

                    add(
                        (base / alias.name).with_suffix(".py")
                    )

        return sorted(deps)

    @staticmethod
    def dependencies(cls):
        return {
            name: p.annotation
            for name, p in inspect.signature(cls.__init__).parameters.items()
            if (
                name != "self"
                and p.annotation is not inspect.Parameter.empty
            )
        }

    @staticmethod
    def is_port_list(annotation):
        return (
            getattr(annotation, "__origin__", None)
            is list
        )

class Framework:
    """
    Kernel del framework.

    Responsabilità:

    - creare namespace dinamici
    - caricare moduli Python
    - registrare descriptor
    """

    def __init__(self):
        self.reflection = Reflection()
        self.components = {}
        self.errors = []


    def _pkg(self, name):

        if not name:
            return None

        if name in sys.modules:
            return sys.modules[name]

        pkg = types.ModuleType(name)

        pkg.__path__ = []

        pkg.__package__ = name.rpartition(".")[0]

        sys.modules[name] = pkg

        if "." in name:

            parent, child = name.rsplit(".", 1)

            setattr(
                self._pkg(parent),
                child,
                pkg
            )

        return pkg


    async def load_module(self,name,path,extra=None,force=False):

        if name in sys.modules and not force:
            return sys.modules[name]

        self._pkg(name.rpartition(".")[0])

        module = types.ModuleType(name)

        module.__file__ = path

        if extra:
            module.__dict__.update(extra)

        sys.modules[name] = module

        if "." in name:

            pkg, short = name.rsplit(".", 1)

            setattr(
                self._pkg(pkg),
                short,
                module
            )

        try:

            code = Path(path).read_bytes()

            exec(
                compile(code, path, "exec"),
                module.__dict__
            )

        except Exception:

            sys.modules.pop(name, None)

            raise

        print(f"[+] {name}")

        return module


    def dependencies_from_class(self, target):
        import inspect
        from typing import get_type_hints, get_args

        dependencies = {}

        hints = get_type_hints(
            target.__init__
        )

        signature = inspect.signature(
            target.__init__
        )

        deps = []

        for name, parameter in signature.parameters.items():

            if name == "self":
                continue

            # ignora **constants
            if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                continue

            annotation = hints.get(name)

            if annotation is None:
                continue

            # caso list[message.Port]
            args = get_args(annotation)

            if args:
                deps.extend(args)
            else:
                deps.append(annotation)

        dependencies[target] = deps

        return dependencies


    def resolve_order(self, nodes, dependencies):

        graph = {
            node: set(dependencies.get(node, []))
            for node in nodes
        }

        return list(
            TopologicalSorter(graph).static_order()
        )

    async def load_core(self,services,ports,extra_by_name=None):

        extra_by_name = extra_by_name or {}

        modules = {
            **services,
            **ports
        }

        graph = {}

        pending = {}

        for name, path in modules.items():
            namespace = (
                f"framework.service.{name}"
                if name in modules
                else
                f"framework.port.{name}"
            )

            pending[name] = Resource(name=namespace,path=path)

            graph[name] = {
                x.split(".")[-1]
                for x in self.reflection.imports(
                    Path(path).read_text()
                )
            } & modules.keys()

        for name in TopologicalSorter(graph).static_order():

            resouce = pending[name]

            await self.load_module(
                resouce.name,
                resouce.path,
                extra_by_name.get(name)
            )

            await self.add(resouce)

            print(f"[✓] Creato {resouce.name}")

    
    async def load(self,resource,extra_by_name={}):

            await self.load_module(
                resource.name,
                resource.path,
                extra_by_name.get(resource.name.split()[-1])
            )

            await self.add(resource)

            print(f"[✓] Creato {resource.name}")

    async def reload(self,resource):

            module = await self.load_module(
                resource.name,
                resource.path,
                resource.extend,
                force=True
            )

            #await self.add(resource)
            resource.module = module

            print(f"[✓] Reload {resource.name}")
            return resource


    async def add(self, resource):

        module = await self.load_module(resource.name,resource.path)
        resource.module = module
        self.components[resource.name] = resource

        print(f"[~] {resource.name}")


    def component(self, name):
        return self.components.get(name)


    def components_iter(self):

        return self.components.values()

    def componetes_ports(self):
        return [
            component
            for component in self.components.values()
            if component.name.startswith("framework.adapter.")
        ]

    def resource_by_path(self, path: str):
        path = str(Path(path))

        for resource in self.components.values():
            if str(Path(resource.path)) == path:
                return resource

        return None

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
                    #print(manager)
                    if hasattr(manager, 'reload'):
                        try:
                            await manager.reload(self._session, message)
                        except Exception as e:
                            print(f"[!] Errore durante il reload in {name}: {e}")
        except asyncio.CancelledError:
            print("[*] Worker di messaggistica terminato.")

    async def startup(self) -> None:
        print("[*] Avvio dei manager del framework...")
        if self._loader.kwargs.get('dev'):
            self._running_tasks.append(asyncio.create_task(self._message_consumer_worker()))

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._stop_event.set)

        for manager in self._managers:
            if hasattr(manager, "startup"):
                res = await manager.startup(self._session)
                if res:
                    if isinstance(res, list):
                        for coro in res: self._running_tasks.append(asyncio.create_task(coro))
                    elif asyncio.iscoroutine(res) or inspect.isawaitable(res):
                        self._running_tasks.append(asyncio.create_task(res))

        print("[+] Framework completamente attivo. In ascolto...")
        await self._stop_event.wait()

    async def shutdown(self) -> None:
        print("\n[*] Spegnimento controllato dei servizi...")
        for manager in reversed(self._managers):
            if hasattr(manager, "shutdown"):
                await manager.shutdown(self._session)
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

    def clear_port(self, iface):
        for k in list(self._ports.keys()):
            if self._match(iface, k):
                self._ports[k].clear()

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
        
        return self._ports[iface]

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
        self.handle = Handle(self)
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
                await self.framework.load(Resource(name=ns, path=path, kind="ADAPTER", config=configs))
    
    def _args(self, dependencies: dict) -> dict:
        lista = []
        for ann in dependencies:
            if ann.__module__.startswith("framework.port"):
                print(ann)
                lista.append(self.container.get_port(ann))
            else:
                if self.container.get(ann):
                    lista.append(self.container.get(ann))
        return lista

    def _build_managers2(self):
        dependencies = {}
        managers = []
        for key in self.managers:
            name = self.managers[key].replace('src/','').replace('.py','').replace('/','.')
            resource = self.framework.component(name)
            manager = resource.module.Manager
            dependencies |= self.framework.dependencies_from_class(manager)
            managers.append(manager)
            #print(dependencies)
            #order = self.framework.resolve_order(dependencies)
            #print(order)
        #print(dependencies)
        order = self.framework.resolve_order(managers,dependencies)
        #print(order)
        
        instances = []

        for item in order:
            if item not in managers:
                continue
            
            if "framework.manager.loader.Loader" in item.__name__:
                self.container.put(item,self,singleton=True)
                continue
            dependencie = dependencies.get(item)
         
            args = self._args(dependencie)
            config = self.current_config.get('manager',{}).get(key,{})
            #print("\n\n\n====================",item,args)
            obj_in = item(*args,**config)

            obj = Handle(obj_in)

            self.container.put(item,obj,singleton=True)

            instances.append(obj)

            print(f"[✓] Manager {item.__module__}.{item.__name__}")
        return instances

    def _build_manager(self, resource, save=True):
        manager_cls = resource.module.Manager

        deps = (
            self.framework
            .dependencies_from_class(manager_cls)
            .get(manager_cls, [])
        )

        args = self._args(deps)

        obj = Handle(
            manager_cls(*args, **(resource.config or {}))
        )

        if save:
            self.container.put(manager_cls, obj)

        return obj

    def _build_managers(self, resources) -> list:

        dependencies = {}
        managers = []

        # Discovery classi e dipendenze
        for resource in resources:

            manager = getattr(
                resource.module,
                "Manager",
                None
            )

            if manager is None:
                print(f"[!] Nessun Manager in {resource.name}")
                continue

            dependencies |= self.framework.dependencies_from_class(manager)

            managers.append(manager)


        # Ordinamento dependency graph
        order = self.framework.resolve_order(
            managers,
            dependencies
        )


        instances = []

        for manager_cls in order:

            if manager_cls not in managers:
                continue


            # caso Loader
            if (
                manager_cls.__module__ == "framework.loader"
                or "loader.Loader" in manager_cls.__qualname__
            ):
                self.container.put(
                    manager_cls,
                    self,
                    singleton=True
                )
                continue


            deps = dependencies.get(
                manager_cls,
                []
            )

            args = self._args(deps)


            # recupera config dal resource
            resource = next(
                (
                    r for r in resources
                    if r.module.Manager is manager_cls
                ),
                None
            )


            config = {}

            if resource:
                config = resource.config or {}


            obj_in = manager_cls(
                *args,
                **config
            )


            obj = Handle(obj_in)


            self.container.put(
                manager_cls,
                obj,
                singleton=True
            )


            instances.append(obj)


            print(
                f"[✓] Manager {manager_cls.__module__}.{manager_cls.__name__}"
            )


        return instances

    def _build_adapters2(self, resources=[]) -> None:
        for resource in resources:
            port = resource.name.split('.')[2]
            interface = self._port_interface(port)
            for adapter in self.current_config.get(port,{}):
                configs = self.current_config.get(port,{}).get(adapter)
                resource = self.framework.component(f"framework.adapter.{port}.{adapter}")
                classe = resource.module.Adapter
                for config in configs:
                    dependencies = self.framework.dependencies_from_class(classe).get(classe)
                    obj_in = classe(*self._args(dependencies), **config)
                    obj = Handle(obj_in)
                    self.container.add_port(interface, obj)

                    print(f"[✓] Adapter {classe.__name__} name={config.get('name')}")
    
    def _build_adapters(self, resources, save=True):
        created = []
        for resource in resources:

            parts = resource.name.split(".")

            if len(parts) < 4:
                continue


            port = parts[2]


            interface = self._port_interface(port)

            if interface is None:
                print(
                    f"[!] Porta non trovata: {port}"
                )
                continue


            adapter_cls = getattr(
                resource.module,
                "Adapter",
                None
            )


            if adapter_cls is None:
                print(
                    f"[!] Nessun Adapter in {resource.name}"
                )
                continue


            configs = resource.config

            if not isinstance(configs, list):
                configs = [configs]


            for config in configs:

                dependencies = (
                    self.framework
                    .dependencies_from_class(adapter_cls)
                    .get(adapter_cls, [])
                )


                args = self._args(
                    dependencies
                )


                obj_in = adapter_cls(
                    *args,
                    **config
                )


                obj = Handle(
                    obj_in
                )

                created.append(obj)

                if save:
                    self.container.add_port(interface,obj)


                print(
                    f"[✓] Adapter {adapter_cls.__name__} "
                    f"name={config.get('name')}"
                )
        return created

    async def reload(self, session, changed_path) -> bool:
        if changed_path.endswith('.py'):
            '''if '/infrastructure/' in changed_path:
                a = changed_path.split('/')
                for i,x in enumerate(a):
                    if x == "infrastructure":
                        index = i
                port = a[index+1]
                interface = f"framework.port.{port}.Port"
                adapters = self.container.get_port(interface)
                print(adapters)
                self.container.clear_port(interface)
                resource = self.framework.resource_by_path(changed_path)
                resource = await self.framework.reload(resource)
                self._build_adapters([resource])
                adapters = self.container.get_port(interface)
                print(adapters)
                return True'''
            if '/infrastructure/' in changed_path:
                port = changed_path.split("/")[changed_path.split("/").index("infrastructure")+1]
                interface = f"framework.port.{port}.Port"

                old_handles = self.container.get_port(interface)
                adapters = self.container.get_port(interface)
                print(adapters)
                resource = self.framework.resource_by_path(changed_path)
                await self.framework.reload(resource)

                new_handles = self._build_adapters([resource],False)

                for old, new in zip(old_handles, new_handles):
                    old.swap(new.obj)

                adapters = self.container.get_port(interface)
                print(adapters)
                return True

            elif '/framework/manager/' in changed_path:
                resource = self.framework.resource_by_path(changed_path)
                await self.framework.reload(resource)

                old = self.container.get(resource.name)

                new = self._build_manager(resource, save=False)

                old.swap(new.obj)

                self.container.remove(resource.name)
                self.container.put(resource.module.Manager, old)
            else:
                print("module",changed_path)

    async def load_schemes(self, directories: list) -> dict:
        return await self.infra.load_schemes(directories)

    async def resource(self, path) -> str:
        return await self.infra.resource(path)

    def file_dependencies(self, file_path: str, root: str = "src") -> list:
        return self.framework.reflection.file_dependencies(file_path, root)

    def get_managers(self) -> dict:
        result = {
            "loader": self.handle
        }

        for resource in self.framework.components_iter():

            # solo manager
            if not resource.name.startswith(
                "framework.manager."
            ):
                continue

            manager_cls = getattr(
                resource.module,
                "Manager",
                None
            )

            if manager_cls is None:
                continue

            obj = self.container.get(manager_cls)

            if obj:
                name = resource.name.split(".")[-1]
                result[name] = obj

        return result

    async def bootstrap(self, config_toml_path: str) -> Application:
        schemes = await self.load_schemes(["src/framework/scheme", "src/application/model"])

        await self.framework.load_core(
            self.services, self.ports,
            extra_by_name={"scheme": {"schemes": schemes, "jinja_env": self.infra.jinja_env}},
        )

        config = tomli.loads(open(config_toml_path['config'], "rb").read().decode())
        self.kwargs = config_toml_path
        self.current_config = config

        print("\n[*] Discovery...")
        manager_resources = []

        for name, path in self.managers.items():

            resource = Resource(
                name=f"framework.manager.{name}",
                path=path,
                kind="MANAGER",
                config=config.get("manager", {}).get(name, {})
            )

            await self.framework.load(resource,)

            manager_resources.append(resource)

        await self._discover_adapters(config)


        print("\n[*] Build...")


        instances = self._build_managers(manager_resources)
        adapters = self._build_adapters(self.framework.componetes_ports())
        #print(self.container.get("framework.manager.messenger.Manager").providers)
        
        defender = self.container.get("framework.manager.defender.Manager")
        await defender.startup()
        session = await defender.session_create()
        print(f"[*] Sessione creata: {session}")

        app = Application(self.container, self, instances, session)
        self.app = app
        return app