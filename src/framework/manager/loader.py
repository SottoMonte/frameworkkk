"""
loader.py — dependency injection framework

Convenzione nomi nel container:
  "persistence"   → modulo framework (src/framework/port/persistence.py)
  "persistences"  → lista di adapter registrati per quel port

Il suffisso "s" è generato da port_list_key() partendo da PORT_REGISTRY,
quindi non può mai disallinearsi con quanto dichiarato nelle spec.
"""

import os
import importlib.util
import asyncio
import signal
import inspect
from graphlib import TopologicalSorter
from dataclasses import dataclass, field

from dependency_injector import containers, providers
import tomli
import traceback

import json
from jinja2 import Environment, BaseLoader
import uuid


# ─────────────────────────────────────────────
# Configurazione globale dei port
# ─────────────────────────────────────────────

PORT_REGISTRY: dict[str, list[str]] = {
    "presentation":   ["defender", "messenger", "executor", "presenter"],
    "persistence":    ["executor"],
    "message":        ["storekeeper", "messenger"],
    "authentication": ["models"],
    "actuator":       [],
    "authorization":  [],
}

def port_list_key(port: str) -> str:
    """'persistence' → 'persistences' (unica fonte del suffisso)."""
    return f"{port}s"


# ─────────────────────────────────────────────
# Struttura Dati Tipizzata per le Specifiche
# ─────────────────────────────────────────────

@dataclass
class ServiceSpec:
    name: str
    path: str
    mod_deps: list[str] = field(default_factory=list)
    cls_deps: list[str] = field(default_factory=list)
    port: str | None = None
    is_class: bool = False
    is_list: bool = False
    config: dict = field(default_factory=dict)
    layer: str = "service"  # Valori ammessi: "service", "manager", "adapter"


# ─────────────────────────────────────────────
# Container — solo storage, zero logica
# ─────────────────────────────────────────────

class Container(containers.DynamicContainer):
    config        = providers.Configuration()
    module_cache  = providers.Singleton(dict)
    loading_stack = providers.Singleton(set)

    # Lambda isolata per ogni port, evita lista condivisa tra istanze
    for _port in PORT_REGISTRY:
        locals()[port_list_key(_port)] = providers.Singleton(lambda: [])
    del _port

    def get(self, name: str):
        attr = getattr(self, name, None)
        if attr is None:
            raise KeyError(f"'{name}' non trovato nel container")
        return attr() if callable(attr) else attr

    def set(self, name: str, obj):
        self.set_provider(name, providers.Singleton(lambda o=obj: o))

    def append_to_port(self, port: str, obj):
        """Aggiunge obj alla lista del port (chiave con suffisso 's')."""
        self.get(port_list_key(port)).append(obj)

    def has(self, name: str) -> bool:
        return hasattr(self, name)


# ─────────────────────────────────────────────
# ModuleLoader — carica e cachea moduli Python
# ─────────────────────────────────────────────

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
        
        # Doppia Iniezione (Native Power) - Mantenuta per retrocompatibilità temporanea
        for k, v in inject.items(): setattr(mod, k, v)
        spec.loader.exec_module(mod)
        for k, v in inject.items(): setattr(mod, k, v)
        
        return mod

    @staticmethod
    def find_class(mod, name):
        for attr_name in (name, name.capitalize(), 'Adapter', 'adapter'):
            if (cls := getattr(mod, attr_name, None)) is not None:
                return cls
        return None


# ─────────────────────────────────────────────
# Builder — istanzia un singolo servizio
# ─────────────────────────────────────────────

class Builder:
    def __init__(self, container: Container, module_loader: ModuleLoader):
        self._c  = container
        self._ml = module_loader

    async def build(self, spec: ServiceSpec):
        mod_inject = self._resolve(spec.mod_deps)
        cls_args   = self._resolve(spec.cls_deps)
        kwargs     = {**cls_args, **spec.config}

        mod = self._ml.load(spec.name, spec.path, inject=mod_inject)
        if spec.is_class:
            cls = self._ml.find_class(mod, spec.name)
            if cls is None:
                raise ImportError(f"Nessuna classe trovata in {spec.path}")
            return cls(**kwargs)

        for k, v in kwargs.items():
            setattr(mod, k, v)
                
        return mod

    def _resolve(self, names: list[str]) -> dict:
        for name in names:
            if not self._c.has(name):
                raise KeyError(f"Dipendenza '{name}' non ancora registrata")
        return {name: self._c.get(name) for name in names}


# ─────────────────────────────────────────────
# BatchSetup — ordina e registra una lista di spec
# ─────────────────────────────────────────────

class BatchSetup:
    def __init__(self, container: Container, builder: Builder):
        self._c = container
        self._b = builder

    async def run(self, specs: list[ServiceSpec], singletons: dict | None = None):
        singletons = singletons or {}
        for name, obj in singletons.items():
            self._c.set(name, obj)
            
        registry   = {s.name: s for s in specs}
        dep_graph  = {
            s.name: list(set(s.mod_deps) | set(s.cls_deps))
            for s in specs
        }

        adapters, managers, services = [], [], []

        for name in TopologicalSorter(dep_graph).static_order():
            if name in singletons or name not in registry:
                continue 

            spec = registry[name]
            
            # Sostituito il vecchio controllo stringa sul path con la proprietà esplicita del layer
            if spec.layer == "adapter":
                adapters.append(name)
            elif spec.layer == "manager":
                managers.append(name)
            else:
                services.append(name)

            try:
                obj = await self._b.build(spec)
                if spec.is_list:
                    self._c.append_to_port(spec.port, obj)
                else:
                    self._c.set(name, obj)
            except Exception as e:
                print(f"[!] Errore durante il caricamento di '{name}': {e}")
                continue

        print(f"[+] Adapters: {adapters}")
        print(f"[+] Managers: {managers}")
        print(f"[+] Services: {services}")


# ─────────────────────────────────────────────
# ProjectLoader — TOML / JSON / DSL → lista di spec
# ─────────────────────────────────────────────

class ProjectLoader:
    def __init__(self, container: Container):
        self._c = container

    def load_schemas(self, directories: list[str]) -> dict:
        raw_data = {}
        for directory in directories:
            if not os.path.exists(directory):
                continue

            for filename in os.listdir(directory):
                if filename.endswith(".json"):
                    name = os.path.splitext(filename)[0]
                    with open(os.path.join(directory, filename), "r") as f:
                        try:
                            raw_data[name] = json.load(f)
                        except json.JSONDecodeError as e:
                            print(f"[!] Errore sintassi JSON in {filename}: {e}")
                            continue

        env = self._c.get('jinja')
        cache = {}
        
        def resolve_schema(name):
            if name in cache and cache[name]: return cache[name]
            raw_obj = raw_data.get(name)
            if not raw_obj: return None
            
            cache[name] = {} 

            def _resolve(val):
                if isinstance(val, dict):
                    return {k: _resolve(v) for k, v in val.items()}
                if isinstance(val, list):
                    return [_resolve(i) for i in val]
                if isinstance(val, str) and "{{" in val:
                    stripped = val.strip()
                    if stripped.startswith("{{") and stripped.endswith("}}") and "|" not in stripped:
                        ref_name = stripped[2:-2].strip()
                        if ref_name in raw_data:
                            return resolve_schema(ref_name)
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

        try:
            from cerberus import schema_registry
            for name, schema in final_schemas.items():
                try: schema_registry.add(name, schema)
                except: pass
        except ImportError:
            pass

        return final_schemas

    async def load_repositories(self, directories):
        raw_data = {}
        interpreter = self._c.get("interpreter") if self._c.has("interpreter") else None
        language = self._c.get("language") if self._c.has("language") else None

        if interpreter and language:
            await interpreter.create_session("loader_repositories", language.DSL_FUNCTIONS)

        for directory in directories:
            if not os.path.exists(directory):
                continue

            for filename in os.listdir(directory):
                if filename.endswith(".dsl"):
                    name = os.path.splitext(filename)[0]
                    with open(os.path.join(directory, filename), "r") as f:
                        try:
                            content = f.read()
                            if interpreter:
                                file_path = f"application/repository/{name}.py"
                                await interpreter.add_file(file_path, content)
                                result = await interpreter.run_session("loader_repositories", file_path)
                                raw_data[name] = result.get('repository') if isinstance(result, dict) and 'repository' in result else result
                            else:
                                raw_data[name] = content
                        except Exception as e:
                            print(f"[!] Errore sintassi DSL in {filename}: {e}")
                            continue
        return raw_data

    def load(self, config_path: str) -> list[ServiceSpec]:
        data = self._read_toml(config_path)
        self._c.config.from_dict(data)
        return [
            self._make_spec(port_name, provider_name, cfg)
            for port_name, services in data.items()
            if port_name in PORT_REGISTRY
            for provider_name, cfg in services.items()
        ]

    def get_config(self):
        return self._c.config()

    def _make_spec(self, port: str, provider: str, cfg: dict) -> ServiceSpec:
        adapter = cfg.get("adapter")
        cfg["provider"] = provider
        return ServiceSpec(
            name=f"{port.lower()}.{provider.lower()}",
            path=f"src/infrastructure/{port}/{adapter}.py",
            mod_deps=[port, "flow"],
            cls_deps=PORT_REGISTRY[port],
            port=port,
            is_class=True,
            is_list=True,
            config=cfg,
            layer="adapter"  # Generato da configurazione esterna di infrastruttura
        )

    @staticmethod
    def _read_toml(path: str) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configurazione non trovata: {path}")
        with open(path, "rb") as f:
            return tomli.load(f)


# ─────────────────────────────────────────────
# Lifecycle — start / stop dei manager
# ─────────────────────────────────────────────

class Lifecycle:
    def __init__(self, container: Container):
        self._c = container

    async def start_all(self, names: list[str]):
        loops_map = {}
        for name in names:
            obj = self._c.get(name)
            if hasattr(obj, "start"):
                res = await obj.start()
                if res:
                    m_loops = []
                    if isinstance(res, list):
                        m_loops.extend(res)
                    elif asyncio.iscoroutine(res) or inspect.isawaitable(res):
                        m_loops.append(res)
                    if m_loops:
                        loops_map[name] = m_loops
        return loops_map

    async def stop_all(self, names: list[str]):
        for name in names:
            obj = self._c.get(name)
            if hasattr(obj, "stop"):
                await obj.stop()


# ─────────────────────────────────────────────
# Spec statiche di bootstrap (Centralizzate e Tipizzate)
# ─────────────────────────────────────────────

_SERVICES: list[ServiceSpec] = [
    ServiceSpec(name="container",      path="src/framework/service/container.py",     layer="service"),
    ServiceSpec(name="scheme",         path="src/framework/service/scheme.py",        mod_deps=["jinja"], layer="service"),
    ServiceSpec(name="flow",           path="src/framework/service/flow.py",          mod_deps=["scheme", "loader"], layer="service"),
    ServiceSpec(name="language",       path="src/framework/service/language.py",      mod_deps=["scheme", "flow"], layer="service"),
    ServiceSpec(name="interpreter",    path="src/framework/service/language.py",      mod_deps=["scheme", "flow"], is_class=True, layer="service"),
    ServiceSpec(name="diagnostic",     path="src/framework/service/diagnostic.py",    mod_deps=["scheme", "flow"], layer="service"),
    ServiceSpec(name="message",        path="src/framework/port/message.py",          mod_deps=["flow"], layer="service"),
    ServiceSpec(name="presentation",   path="src/framework/port/presentation.py",     mod_deps=["scheme", "loader"], layer="service"),
    ServiceSpec(name="persistence",    path="src/framework/port/persistence.py",      mod_deps=["flow"], layer="service"),
    ServiceSpec(name="authentication", path="src/framework/port/authentication.py",   mod_deps=["flow"], layer="service"),
    ServiceSpec(name="factory",        path="src/framework/service/factory.py",       mod_deps=["flow", "jinja", "scheme"], layer="service"),
]

_MANAGERS: list[ServiceSpec] = [
    ServiceSpec(name="loader",      path="src/framework/manager/loader.py",      mod_deps=["container"], is_class=True, layer="manager"),
    ServiceSpec(name="messenger",   path="src/framework/manager/messenger.py",   mod_deps=["flow"], cls_deps=["executor", "messages"], is_class=True, layer="manager"),
    ServiceSpec(name="executor",    path="src/framework/manager/executor.py",    mod_deps=["flow"], cls_deps=["defender", "language", "models", "interpreter"], is_class=True, layer="manager"),
    ServiceSpec(name="defender",    path="src/framework/manager/defender.py",    mod_deps=["flow"], cls_deps=["language", "loader", "authentications", "models", "interpreter"], is_class=True, layer="manager"),
    ServiceSpec(name="tester",      path="src/framework/manager/tester.py",      mod_deps=["language", "flow", "diagnostic"], cls_deps=["loader", "defender", "executor", "messenger", "models"], is_class=True, layer="manager"),
    ServiceSpec(name="storekeeper", path="src/framework/manager/storekeeper.py", mod_deps=["flow", "factory"], cls_deps=["executor", "persistences", "repositories"], is_class=True, layer="manager"),
    ServiceSpec(name="presenter",   path="src/framework/manager/presenter.py",   cls_deps=["executor", "presentations"], is_class=True, layer="manager"),
]


# ─────────────────────────────────────────────
# Loader — orchestratore pubblico
# ─────────────────────────────────────────────

class Loader:
    def __init__(self, **config):
        self.config = config

        self._container  = Container()
        self._mod_loader = ModuleLoader(self._container)
        self._builder    = Builder(self._container, self._mod_loader)
        self._batch      = BatchSetup(self._container, self._builder)
        self._project    = ProjectLoader(self._container)
        self._lifecycle  = Lifecycle(self._container)
        self.ready        = asyncio.Event()

        self._jinja = Environment(loader=BaseLoader())
        self._jinja.filters['tojson'] = lambda obj: json.dumps(obj)
        self._jinja.globals['uuid4'] = lambda: str(uuid.uuid4())
        self._jinja.filters['get'] = lambda d, k, default=None: self._container.get('scheme').get(d, k, default)
        
        self._container.set('jinja', self._jinja)

    def get(self, name: str):
        return self._container.get(name)

    def get_model(self, name: str):
        return self._container.get("models").get(name)

    async def resource(self, path: str):
        base_path = os.environ.get("BASE_PATH", os.getcwd()) 
        if not path.startswith("src"):
            path = "src/" + path
        path = base_path + "/" + path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Risorsa non trovata: {path}")

        if path.endswith(".py"):
            name = os.path.splitext(os.path.basename(path))[0]
            inject = {k: self._container.get(k) for k in PORT_REGISTRY if self._container.has(k)}
            return self._mod_loader.load(name, path, inject=inject)

        with open(path) as f:
            return f.read()

    async def bootstrap(self, args):
        print("[*] Framework bootstrapped. Running...")
        project_specs = self._project.load("pyproject.toml") 
        config = self._project.get_config()

        # Configurazione degli argomenti dinamici via properties della dataclass
        for mgr in _MANAGERS:
            if mgr.name == "defender":
                mgr.config.update({'args': args, 'project': config.get('project', {})})
            elif mgr.name == "tester":
                mgr.config.update({'args': args})

        application_models = self._project.load_schemas(["src/framework/scheme/", "src/application/model/"])
        print(f"[+] Models: {list(application_models.keys())}")

        application_repositories = {}

        await self._batch.run(
            _SERVICES + _MANAGERS + project_specs,
            singletons={
                "loader":       self,
                "container":    self._container,
                "models":       application_models,
                "repositories": application_repositories,
            },
        )

        loaded_repos = await self._project.load_repositories(["src/application/repository/"])
        application_repositories.update(loaded_repos)
        print(f"[+] Repositories: {list(application_repositories.keys())}")

        stop_event = asyncio.Event()
        loop       = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: stop_event.set())

        manager_names = [s.name for s in _MANAGERS]
        try:
            loops_map = await self._lifecycle.start_all(manager_names)
            self.ready.set()
            
            for name, loops in loops_map.items():
                if name != "tester":
                    for loop_coro in loops:
                        asyncio.create_task(loop_coro)
            await asyncio.sleep(1)
            
            if "tester" in loops_map:
                for loop_coro in loops_map["tester"]:
                    asyncio.create_task(loop_coro)
                
            await stop_event.wait()
        except Exception as e:
            print(f"[!] Errore: {e}")
            traceback.print_exc()
        finally:
            await self._lifecycle.stop_all(manager_names)
            print("[*] Framework spento correttamente.")