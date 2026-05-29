import os
import importlib.util
import asyncio
import signal
import inspect
import json
import uuid
import traceback
from graphlib import TopologicalSorter

from dependency_injector import containers, providers
import tomli
from jinja2 import Environment, BaseLoader

# ─────────────────────────────────────────────
# 1. MANIFESTO E CONFIGURAZIONE (L'unica parte da modificare per aggiungere/togliere roba)
# ─────────────────────────────────────────────

class FrameworkManifest:
    """Registro centrale del framework. Aggiungi/rimuovi funzionalità solo qui."""
    
    PORTS: dict[str, list[str]] = {
        "presentation":   ["defender", "messenger", "executor", "presenter"],
        "persistence":    ["executor"],
        "message":        ["storekeeper", "messenger"],
        "authentication": ["models"],
        "actuator":       [],
        "authorization":  [],
    }

    SERVICES: list[dict] = [
        {"name": "container",      "path": "src/framework/service/container.py",      "mod_deps": [],                  "is_class": False, "config": {}},
        {"name": "scheme",         "path": "src/framework/service/scheme.py",         "mod_deps": ["jinja"],           "is_class": False, "config": {}},
        {"name": "flow",           "path": "src/framework/service/flow.py",           "mod_deps": ["scheme", "loader"],"is_class": False, "config": {}},
        {"name": "language",       "path": "src/framework/service/language.py",       "mod_deps": ["scheme", "flow"],  "is_class": False, "config": {}},
        {"name": "interpreter",    "path": "src/framework/service/language.py",       "mod_deps": ["scheme", "flow"],  "is_class": True,  "config": {}},
        {"name": "diagnostic",     "path": "src/framework/service/diagnostic.py",     "mod_deps": ["scheme", "flow"],  "is_class": False, "config": {}},
        {"name": "message",        "path": "src/framework/port/message.py",           "mod_deps": ["flow"],            "is_class": False, "config": {}},
        {"name": "presentation",   "path": "src/framework/port/presentation.py",      "mod_deps": ["scheme","loader"], "is_class": False, "config": {}},
        {"name": "persistence",    "path": "src/framework/port/persistence.py",       "mod_deps": ["flow"],            "is_class": False, "config": {}},
        {"name": "authentication", "path": "src/framework/port/authentication.py",    "mod_deps": ["flow"],            "is_class": False, "config": {}},
        {"name": "factory",        "path": "src/framework/service/factory.py",        "mod_deps": ["flow", "jinja", "scheme"], "is_class": False, "config": {}},
    ]

    @staticmethod
    def get_managers(args, project_config: dict) -> list[dict]:
        return [
            {"name": "loader",      "path": "src/framework/manager/loader.py",      "mod_deps": ["container"], "cls_deps": [], "is_class": True, "config": {}},
            {"name": "messenger",   "path": "src/framework/manager/messenger.py",   "mod_deps": ["flow"], "cls_deps": ["executor", "messages"], "is_class": True, "config": {}},
            {"name": "executor",    "path": "src/framework/manager/executor.py",    "mod_deps": ["flow"], "cls_deps": ["defender", "language", "models", "interpreter"], "is_class": True, "config": {}},
            {"name": "defender",    "path": "src/framework/manager/defender.py",    "mod_deps": ["flow"], "cls_deps": ["language", "loader", "authentications", "models", "interpreter"], "is_class": True, "config": {'args': args, 'project': project_config}},
            {"name": "tester",      "path": "src/framework/manager/tester.py",      "mod_deps": ["language","flow","diagnostic"], "cls_deps": ["loader", "defender", "executor", "messenger", "models"], "is_class": True, "config": {'args': args}},
            {"name": "storekeeper", "path": "src/framework/manager/storekeeper.py", "mod_deps": ["flow","factory"], "cls_deps": ["executor", "persistences","repositories"], "is_class": True, "config": {}},
            {"name": "presenter",   "path": "src/framework/manager/presenter.py",   "mod_deps": [], "cls_deps": ["executor", "presentations"], "is_class": True, "config": {}},
        ]

    @staticmethod
    def port_list_key(port: str) -> str:
        return f"{port}s"


# ─────────────────────────────────────────────
# 2. CORE DI E CONTAINER
# ─────────────────────────────────────────────

class Container(containers.DynamicContainer):
    config        = providers.Configuration()
    module_cache  = providers.Singleton(dict)
    loading_stack = providers.Singleton(set)

    for _port in FrameworkManifest.PORTS:
        locals()[FrameworkManifest.port_list_key(_port)] = providers.Singleton(lambda: [])
    del _port

    def get(self, name: str):
        attr = getattr(self, name, None)
        if attr is None: raise KeyError(f"'{name}' non trovato nel container")
        return attr() if callable(attr) else attr

    def set(self, name: str, obj):
        self.set_provider(name, providers.Singleton(lambda o=obj: o))

    def append_to_port(self, port: str, obj):
        self.get(FrameworkManifest.port_list_key(port)).append(obj)

    def has(self, name: str) -> bool:
        return hasattr(self, name)


class ModuleLoader:
    def __init__(self, container: Container):
        self._container = container

    def load(self, name: str, path: str, inject: dict | None = None):
        cache = self._container.get("module_cache")
        if path not in cache:
            cache[path] = self._exec(name, path, inject or {})
        return cache[path]

    @staticmethod
    def _exec(name: str, path: str, inject: dict):
        spec = importlib.util.spec_from_file_location(name, path)
        mod  = importlib.util.module_from_spec(spec)
        
        for k, v in inject.items(): setattr(mod, k, v)
        spec.loader.exec_module(mod)
        for k, v in inject.items(): setattr(mod, k, v)
        
        return mod

    @staticmethod
    def find_class(mod, name: str):
        for candidate in [name, name.capitalize(), 'Adapter', 'adapter']:
            if cls := getattr(mod, candidate, None):
                return cls
        return None


# ─────────────────────────────────────────────
# 3. BUILDER E BATCH SETUP
# ─────────────────────────────────────────────

class Builder:
    def __init__(self, container: Container, module_loader: ModuleLoader):
        self._c  = container
        self._ml = module_loader

    async def build(self, spec: dict):
        mod_inject = self._resolve(spec.get("mod_deps", []))
        cls_args   = self._resolve(spec.get("cls_deps", []))
        kwargs     = {**cls_args, **spec.get("config", {})}

        mod = self._ml.load(spec["name"], spec["path"], inject=mod_inject)
        
        if spec.get("is_class"):
            cls = self._ml.find_class(mod, spec["name"])
            if not cls: raise ImportError(f"Nessuna classe trovata in {spec['path']}")
            return cls(**kwargs)

        for k, v in kwargs.items():
            setattr(mod, k, v)
        return mod

    def _resolve(self, names: list[str]) -> dict:
        return {name: self._c.get(name) for name in names if self._c.has(name)}


class BatchSetup:
    def __init__(self, container: Container, builder: Builder):
        self._c = container
        self._b = builder

    async def run(self, specs: list[dict], singletons: dict | None = None):
        for name, obj in (singletons or {}).items():
            self._c.set(name, obj)
            
        registry  = {s["name"]: s for s in specs}
        dep_graph = {s["name"]: list(set(s.get("mod_deps", [])) | set(s.get("cls_deps", []))) for s in specs}

        adapters, managers, services = [], [], []

        for name in TopologicalSorter(dep_graph).static_order():
            if name in (singletons or {}) or name not in registry:
                continue

            spec = registry[name]
            path = spec.get("path", "")
            if 'infrastructure' in path: adapters.append(name)
            elif 'manager' in path: managers.append(name)
            else: services.append(name)

            try:
                obj = await self._b.build(spec)
                if spec.get("is_list"):
                    self._c.append_to_port(spec["port"], obj)
                else:
                    self._c.set(name, obj)
            except Exception as e:
                print(f"[!] Errore durante il caricamento di '{name}': {e}")

        print(f"[+] Adapters: {adapters}\n[+] Managers: {managers}\n[+] Services: {services}")


# ─────────────────────────────────────────────
# 4. GESTIONE RISORSE (SCHEMI, REPO, TOML) 
# ─────────────────────────────────────────────

class SchemaLoader:
    """Isolata la logica di rendering Jinja e JSON loading."""
    def __init__(self, container: Container):
        self._c = container

    def load_schemas(self, directories: list[str]) -> dict:
        raw_data = {}
        for directory in filter(os.path.exists, directories):
            for filename in filter(lambda f: f.endswith(".json"), os.listdir(directory)):
                name = os.path.splitext(filename)[0]
                try:
                    with open(os.path.join(directory, filename), "r") as f:
                        raw_data[name] = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"[!] Errore sintassi JSON in {filename}: {e}")

        env = self._c.get('jinja')
        cache = {}

        def resolve_schema(name):
            if name in cache and cache[name]: return cache[name]
            raw_obj = raw_data.get(name)
            if not raw_obj: return None
            cache[name] = {} 

            def _resolve(val):
                if isinstance(val, dict): return {k: _resolve(v) for k, v in val.items()}
                if isinstance(val, list): return [_resolve(i) for i in val]
                if isinstance(val, str) and "{{" in val:
                    stripped = val.strip()
                    if stripped.startswith("{{") and stripped.endswith("}}") and "|" not in stripped:
                        ref_name = stripped[2:-2].strip()
                        if ref_name in raw_data: return resolve_schema(ref_name)
                        if ref_name in env.globals:
                            g = env.globals[ref_name]
                            return g() if callable(g) else g
                    ctx = {**env.globals, **raw_data, **{k: v for k, v in cache.items() if v}}
                    return env.from_string(val).render(**ctx)
                return val

            resolved = _resolve(raw_obj)
            cache[name] = resolved
            return resolved

        final_schemas = {name: resolve_schema(name) for name in raw_data}
        self._register_cerberus(final_schemas)
        return final_schemas

    @staticmethod
    def _register_cerberus(schemas: dict):
        try:
            from cerberus import schema_registry
            for name, schema in schemas.items():
                try: schema_registry.add(name, schema)
                except: pass
        except ImportError:
            pass


class RepositoryLoader:
    """Isolata la logica di caricamento dei DSL."""
    def __init__(self, container: Container):
        self._c = container

    async def load_repositories(self, directories: list[str]) -> dict:
        raw_data = {}
        interpreter = self._c.get("interpreter") if self._c.has("interpreter") else None
        language = self._c.get("language") if self._c.has("language") else None

        if interpreter and language:
            await interpreter.create_session("loader_repositories", language.DSL_FUNCTIONS)

        for directory in filter(os.path.exists, directories):
            for filename in filter(lambda f: f.endswith(".dsl"), os.listdir(directory)):
                name = os.path.splitext(filename)[0]
                try:
                    with open(os.path.join(directory, filename), "r") as f:
                        content = f.read()
                        if interpreter:
                            file_path = f"application/repository/{name}.py"
                            await interpreter.add_file(file_path, content)
                            result = await interpreter.run_session("loader_repositories", file_path)
                            raw_data[name] = result.get('repository', result) if isinstance(result, dict) else result
                        else:
                            raw_data[name] = content
                except Exception as e:
                    print(f"[!] Errore DSL in {filename}: {e}")
        return raw_data


class ConfigLoader:
    """Isolata la logica per il TOML."""
    def __init__(self, container: Container):
        self._c = container

    def load(self, config_path: str) -> list[dict]:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configurazione non trovata: {config_path}")
        with open(config_path, "rb") as f:
            data = tomli.load(f)
        
        self._c.config.from_dict(data)
        
        return [
            self._make_spec(port, provider, cfg)
            for port, services in data.items() if port in FrameworkManifest.PORTS
            for provider, cfg in services.items()
        ]

    def _make_spec(self, port: str, provider: str, cfg: dict) -> dict:
        cfg["provider"] = provider
        return {
            "name":     f"{port.lower()}.{provider.lower()}",
            "path":     f"src/infrastructure/{port}/{cfg.get('adapter')}.server.py",
            "mod_deps": [port, "flow"],
            "cls_deps": FrameworkManifest.PORTS[port],
            "port":     port,
            "is_class": True,
            "is_list":  True,
            "config":   cfg,
        }


# ─────────────────────────────────────────────
# 5. LIFECYCLE
# ─────────────────────────────────────────────

class Lifecycle:
    def __init__(self, container: Container):
        self._c = container

    async def start_all(self, names: list[str]) -> dict:
        loops_map = {}
        for name in names:
            obj = self._c.get(name)
            if hasattr(obj, "start"):
                res = await obj.start()
                m_loops = []
                if isinstance(res, list): m_loops.extend(res)
                elif asyncio.iscoroutine(res) or inspect.isawaitable(res): m_loops.append(res)
                
                if m_loops: loops_map[name] = m_loops
        return loops_map

    async def stop_all(self, names: list[str]):
        for name in names:
            obj = self._c.get(name)
            if hasattr(obj, "stop"): await obj.stop()


# ─────────────────────────────────────────────
# 6. ORCHESTRATORE PUBBLICO (Facade)
# ─────────────────────────────────────────────

class Loader:
    def __init__(self, **config):
        self.config = config
        self.ready  = asyncio.Event()

        # Istanziazione moduli isolati
        self._container  = Container()
        self._mod_loader = ModuleLoader(self._container)
        self._builder    = Builder(self._container, self._mod_loader)
        self._batch      = BatchSetup(self._container, self._builder)
        self._lifecycle  = Lifecycle(self._container)
        
        self._schema_ldr = SchemaLoader(self._container)
        self._repo_ldr   = RepositoryLoader(self._container)
        self._config_ldr = ConfigLoader(self._container)

        self._init_jinja()

    def _init_jinja(self):
        jinja_env = Environment(loader=BaseLoader())
        jinja_env.filters['tojson'] = lambda obj: json.dumps(obj)
        jinja_env.globals['uuid4']  = lambda: str(uuid.uuid4())
        jinja_env.filters['get']    = lambda d, k, default=None: self._container.get('scheme').get(d, k, default)
        self._container.set('jinja', jinja_env)

    def get(self, name: str):
        return self._container.get(name)

    def get_model(self, name: str):
        return self._container.get("models").get(name)

    async def resource(self, path: str):
        base_path = os.environ.get("BASE_PATH", os.getcwd()) 
        path = f"{base_path}/{path if path.startswith('src') else 'src/' + path}"
        
        if not os.path.exists(path): raise FileNotFoundError(f"Risorsa non trovata: {path}")

        if path.endswith(".py"):
            name = os.path.splitext(os.path.basename(path))[0]
            inject = {k: self._container.get(k) for k in FrameworkManifest.PORTS if self._container.has(k)}
            return self._mod_loader.load(name, path, inject=inject)

        with open(path) as f: return f.read()

    async def bootstrap(self, args):
        print("[*] Framework bootstrapped. Running...")
        
        # 1. Carica configurazioni esterne e schemi
        project_specs = self._config_ldr.load("pyproject.toml")
        project_cfg   = self._container.config()
        
        app_models = self._schema_ldr.load_schemas(["src/framework/scheme/", "src/application/model/"])
        print(f"[+] Models: {list(app_models.keys())}")

        app_repos = {}
        managers_specs = FrameworkManifest.get_managers(args, project_cfg.get('project', {}))

        # 2. Inietta tutto nel batch setup
        await self._batch.run(
            FrameworkManifest.SERVICES + managers_specs + project_specs,
            singletons={
                "loader":       self,
                "container":    self._container,
                "models":       app_models,
                "repositories": app_repos,
            },
        )

        # 3. Carica Repositories a valle del batch
        loaded_repos = await self._repo_ldr.load_repositories(["src/application/repository/"])
        app_repos.update(loaded_repos)
        print(f"[+] Repositories: {list(app_repos.keys())}")

        # 4. Gestione Eventi e Ciclo di Vita
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _on_signal():
            print("\n[!] Shutdown richiesto.")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)

        manager_names = [s["name"] for s in managers_specs]
        
        try:
            loops_map = await self._lifecycle.start_all(manager_names)
            self.ready.set()
            
            # Start background tasks
            for name, loops in loops_map.items():
                if name != "tester":
                    for loop_coro in loops: asyncio.create_task(loop_coro)
            
            await asyncio.sleep(1)
            
            # Start tester last
            if "tester" in loops_map:
                for loop_coro in loops_map["tester"]: asyncio.create_task(loop_coro)
                
            await stop_event.wait()
        except Exception as e:
            print(f"[!] Errore critico: {e}")
            traceback.print_exc()
        finally:
            await self._lifecycle.stop_all(manager_names)
            print("[*] Framework spento correttamente.")