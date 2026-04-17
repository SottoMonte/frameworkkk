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

from dependency_injector import containers, providers
import tomli
import traceback

import json
from jinja2 import Environment, BaseLoader
import uuid


# ─────────────────────────────────────────────
# Configurazione globale dei port
# Aggiungere/rimuovere un port: solo questa dict.
# ─────────────────────────────────────────────

PORT_REGISTRY: dict[str, list[str]] = {
    "presentation":   ["defender", "messenger","executor","presenter"],
    "persistence":    ["executor"],
    "message":        ["storekeeper", "messenger"],
    "authentication": ["models"],
    "actuator":       [],
    "authorization":  [],
}

def port_list_key(port: str) -> str:
    """'persistence' → 'persistences'  (unica fonte del suffisso)."""
    return f"{port}s"


# ─────────────────────────────────────────────
# Container — solo storage, zero logica
# ─────────────────────────────────────────────

class Container(containers.DynamicContainer):
    config        = providers.Configuration()
    module_cache  = providers.Singleton(dict)
    loading_stack = providers.Singleton(set)

    # FIX: lambda isolata per ogni port, evita lista condivisa tra istanze
    for _port in PORT_REGISTRY:
        locals()[port_list_key(_port)] = providers.Singleton(lambda: [])
    del _port

    def get(self, name: str):
        attr = getattr(self, name, None)
        if attr is None:
            raise KeyError(f"'{name}' non trovato nel container")
        return attr() if callable(attr) else attr

    def set(self, name: str, obj):
        # FIX: set_provider registra il provider in modo che dependency_injector
        # lo tracci correttamente, a differenza di setattr che lo rendeva invisibile
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
        
        # Doppia Iniezione (Native Power)
        # 1. Prima dell'esecuzione per supportare definizioni top-level
        for k, v in inject.items(): setattr(mod, k, v)
            
        spec.loader.exec_module(mod)
        
        # 2. Dopo l'esecuzione per garantire la persistenza contro sovrascritture o reset del namespace
        for k, v in inject.items(): setattr(mod, k, v)
        
        return mod

    @staticmethod
    def find_class(mod, name):
        ok = getattr(mod, name, None)
        if not ok:
            ok = getattr(mod, name.capitalize(), None)
        if not ok:
            ok = getattr(mod, 'Adapter', None)
        if not ok:
            ok = getattr(mod, 'adapter', None)
        return ok


# ─────────────────────────────────────────────
# Builder — istanzia un singolo servizio
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
            if cls is None:
                raise ImportError(f"Nessuna classe trovata in {spec['path']}")
            return cls(**kwargs)

        for k, v in kwargs.items():
            setattr(mod, k, v)
                
        return mod

    def _resolve(self, names: list[str]) -> dict:
        result = {}
        for name in names:
            if not self._c.has(name):
                raise KeyError(f"Dipendenza '{name}' non ancora registrata")
            result[name] = self._c.get(name)
        return result


# ─────────────────────────────────────────────
# BatchSetup — ordina e registra una lista di spec
# ─────────────────────────────────────────────

class BatchSetup:
    def __init__(self, container: Container, builder: Builder):
        self._c = container
        self._b = builder

    async def run(self, specs: list[dict], singletons: dict | None = None):
        singletons = singletons or {}
        for name, obj in singletons.items():
            self._c.set(name, obj)
        registry   = {s["name"]: s for s in specs}
        dep_graph  = {
            s["name"]: list(set(s.get("mod_deps", [])) | set(s.get("cls_deps", [])))
            for s in specs
        }

        adapters, managers, services = [], [], []

        for name in TopologicalSorter(dep_graph).static_order():

            if name in singletons:
                self._c.set(name, singletons[name])
                continue
            if name not in registry:
                continue

            if 'src/infrastructure' in registry[name].get("path"):
                adapters.append(name)
            elif 'src/framework/manager' in registry[name].get("path"):
                managers.append(name)
            else:
                services.append(name)

            spec = registry[name]
            try:
                obj  = await self._b.build(spec)

                if spec.get("is_list"):
                    self._c.append_to_port(spec["port"], obj)
                else:
                    self._c.set(name, obj)
            except Exception as e:
                print(f"[!] Errore durante il caricamento di '{name}': {e}")
                # traceback.print_exc()
                continue

        print(f"[+] Adapters: {adapters}")
        print(f"[+] Managers: {managers}")
        print(f"[+] Services: {services}")


# ─────────────────────────────────────────────
# ProjectLoader — TOML → lista di spec
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
            
            # Evitiamo loop infiniti mettendo un segnaposto
            cache[name] = {} 

            def _resolve(val):
                if isinstance(val, dict):
                    return {k: _resolve(v) for k, v in val.items()}
                if isinstance(val, list):
                    return [_resolve(i) for i in val]
                if isinstance(val, str) and "{{" in val:
                    stripped = val.strip()
                    # Riferimento diretto: "{{ user }}"
                    if stripped.startswith("{{") and stripped.endswith("}}") and "|" not in stripped:
                        ref_name = stripped[2:-2].strip()
                        if ref_name in raw_data:
                            return resolve_schema(ref_name)
                        if ref_name in env.globals:
                            g = env.globals[ref_name]
                            return g() if callable(g) else g
                    
                    # Rendering Jinja standard
                    # Usiamo i raw_data come contesto, ma se uno schema è già in cache usiamo quello
                    ctx = {**env.globals, **raw_data, **{k: v for k, v in cache.items() if v}}
                    return env.from_string(val).render(**ctx)
                return val

            resolved = _resolve(raw_obj)
            cache[name] = resolved
            return resolved

        final_schemas = {}
        for name in raw_data:
            final_schemas[name] = resolve_schema(name)

        # Registrazione globale in Cerberus per riferimenti diretti via stringa
        try:
            from cerberus import schema_registry
            for name, schema in final_schemas.items():
                try:
                    schema_registry.add(name, schema)
                except:
                    pass
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
                                if isinstance(result, dict) and 'repository' in result:
                                    raw_data[name] = result.get('repository')
                                else:
                                    raw_data[name] = result
                            else:
                                raw_data[name] = content
                        except Exception as e:
                            print(f"[!] Errore sintassi DSL in {filename}: {e}")
                            continue
        return raw_data

    def load(self, config_path: str) -> list[dict]:
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

    def _make_spec(self, port: str, provider: str, cfg: dict) -> dict:
        adapter = cfg.get("adapter")
        cfg["provider"] = provider
        return {
            "name":     f"{port.lower()}.{provider.lower()}",
            "path":     f"src/infrastructure/{port}/{adapter}.py",
            "mod_deps": [port, "flow"],
            "cls_deps": PORT_REGISTRY[port],
            "port":     port,
            "is_class": True,
            "is_list":  True,
            "config":   cfg,
        }

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
# Spec statiche di bootstrap
#
# cls_deps usa "persistences" / "presentations" ecc. — il suffisso
# è coerente con quanto registrato dal Container tramite port_list_key().
# ─────────────────────────────────────────────

_SERVICES: list[dict] = [
    {"name": "container",       "path": "src/framework/service/container.py",      "mod_deps": [],                   "is_class": False, "config": {}},
    {"name": "scheme",          "path": "src/framework/service/scheme.py",         "mod_deps": ["jinja"],            "is_class": False, "config": {}},
    {"name": "flow",            "path": "src/framework/service/flow.py",           "mod_deps": ["scheme", "loader"], "is_class": False, "config": {}},
    {"name": "language",        "path": "src/framework/service/language.py",       "mod_deps": ["scheme", "flow"],   "is_class": False, "config": {}},
    {"name": "interpreter",     "path": "src/framework/service/language.py",       "mod_deps": ["scheme", "flow"],   "is_class": True,  "config": {}},
    {"name": "diagnostic",      "path": "src/framework/service/diagnostic.py",     "mod_deps": ["scheme", "flow"],   "is_class": False, "config": {}},
    {"name": "message",         "path": "src/framework/port/message.py",           "mod_deps": ["flow"],             "is_class": False, "config": {}},
    {"name": "presentation",    "path": "src/framework/port/presentation.py",      "mod_deps": ["scheme","loader"],  "is_class": False, "config": {}},
    {"name": "persistence",     "path": "src/framework/port/persistence.py",       "mod_deps": ["flow"],             "is_class": False, "config": {}},
    {"name": "authentication",  "path": "src/framework/port/authentication.py",    "mod_deps": ["flow"],             "is_class": False, "config": {}},
    {"name": "factory",         "path": "src/framework/service/factory.py",        "mod_deps": ["flow", "jinja", "scheme"], "is_class": False, "config": {}},
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

        # Inizializzazione Ambiente Jinja2 Centrale
        self._jinja = Environment(loader=BaseLoader())
        self._jinja.filters['tojson'] = lambda obj: json.dumps(obj)
        self._jinja.globals['uuid4'] = lambda: str(uuid.uuid4())
        
        # Filtro 'get' nativo: delegazione pigra allo Scheme Service
        self._jinja.filters['get'] = lambda d, k, default=None: self._container.get('scheme').get(d, k, default)
        
        self._container.set('jinja', self._jinja)

    def get(self, name: str):
        return self._container.get(name)

    def get_model(self, name: str):
        # FIX: chiave corretta "models" (plurale), rimossa print di debug
        
        return self._container.get("models").get(name)

    async def resource(self, path: str):
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
        # nota: '--test' con filtro (es. '--test managers') non avvia il server,
        # l'argomento successivo è consumato dal tester e non interferisce qui.
        config = self._project.get_config()

        application_models = self._project.load_schemas(["src/framework/scheme/", "src/application/model/"])
        print(f"[+] Models: {list(application_models.keys())}")

        application_repositories = {}

        _MANAGERS: list[dict] = [
            {"name": "loader",      "path": "src/framework/manager/loader.py",      "mod_deps": ["container"],                    "cls_deps": [],                                                        "is_class": True, "config": {}},
            {"name": "messenger",   "path": "src/framework/manager/messenger.py",   "mod_deps": ["flow"],                         "cls_deps": ["executor", "messages"],                                  "is_class": True, "config": {}},
            {"name": "executor",    "path": "src/framework/manager/executor.py",    "mod_deps": ["flow"],                         "cls_deps": ["defender", "language", "models", "interpreter"],                        "is_class": True, "config": {}},
            {"name": "defender",    "path": "src/framework/manager/defender.py",    "mod_deps": ["flow"],                         "cls_deps": ["language", "loader", "authentications", "models", "interpreter"],       "is_class": True, "config": {'args': args, 'project': config.get('project', {})}},
            {"name": "tester",      "path": "src/framework/manager/tester.py",      "mod_deps": ["language","flow","diagnostic"], "cls_deps": ["loader", "defender", 'executor', "messenger", "models"],             "is_class": True, "config": {'args': args}},
            {"name": "storekeeper", "path": "src/framework/manager/storekeeper.py", "mod_deps": ["flow","factory"],                               "cls_deps": ["executor", "persistences","repositories"],                              "is_class": True, "config": {}},
            {"name": "presenter",   "path": "src/framework/manager/presenter.py",   "mod_deps": [],                               "cls_deps": ["executor", "presentations"],                             "is_class": True, "config": {}},
        ]

        await self._batch.run(
            _SERVICES + _MANAGERS + project_specs,
            singletons={
                "loader":    self,
                "container": self._container,
                "models":    application_models,
                "repositories": application_repositories,
            },
        )

        loaded_repos = await self._project.load_repositories(["src/application/repository/"])
        application_repositories.update(loaded_repos)
        print(f"[+] Repositories: {list(application_repositories.keys())}")

        stop_event = asyncio.Event()
        loop       = asyncio.get_running_loop()

        def _on_signal():
            print("\n[!] Shutdown richiesto.")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)

        manager_names = [s["name"] for s in _MANAGERS]
        try:
            loops_map = await self._lifecycle.start_all(manager_names)
            self.ready.set()
            
            # 1. Avviamo tutti i processi di background tranne il tester
            for name, loops in loops_map.items():
                if name != "tester":
                    for loop_coro in loops:
                        asyncio.create_task(loop_coro)
            await asyncio.sleep(1)
            # 2. Avviamo il tester per ultimo
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