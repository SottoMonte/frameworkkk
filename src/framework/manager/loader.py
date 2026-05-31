import os
import sys
import importlib.util
import asyncio
import signal
import inspect
import traceback
import json
import uuid
from dataclasses import dataclass, field
from typing import Type, TypeVar, Any, Protocol, runtime_checkable, Callable
from graphlib import TopologicalSorter
from jinja2 import Environment, BaseLoader
import tomli

T = TypeVar('T')

# ─────────────────────────────────────────────
# 1. INTERFACCE E PROTOCOLLI (Type Safety)
# ─────────────────────────────────────────────

@runtime_checkable
class LifecycleComponent(Protocol):
    """Interfaccia per qualsiasi componente con un ciclo di vita attivo."""
    async def start(self) -> Any: ...
    async def stop(self) -> None: ...


class ModuleExtension(Protocol):
    """Permette a moduli esterni di registrare servizi in modo dichiarativo."""
    def configure(self, container: "Container") -> None: ...


# ─────────────────────────────────────────────
# 2. STRUTTURE DATI TIPIZZATE
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class ServiceSpec:
    name: str
    path: str
    layer: str = "service"  # "service", "manager", "adapter"
    is_class: bool = False
    is_list: bool = False
    port_interface: Type | None = None
    config: dict[str, Any] = field(default_factory=dict)

_FRAMEWORK_SERVICES = [
    ServiceSpec(name="container",    path="src/framework/service/container.py",     layer="service"),
    ServiceSpec(name="scheme",       path="src/framework/service/scheme.py",        layer="service"),
    ServiceSpec(name="flow",         path="src/framework/service/flow.py",          layer="service"),
    ServiceSpec(name="language",     path="src/framework/service/language.py",      layer="service"),
    ServiceSpec(name="interpreter",  path="src/framework/service/language.py",      layer="service", is_class=True),
    ServiceSpec(name="diagnostic",   path="src/framework/service/diagnostic.py",    layer="service"),
    ServiceSpec(name="message",      path="src/framework/port/message.py",          layer="service"),
    ServiceSpec(name="presentation", path="src/framework/port/presentation.py",     layer="service"),
    ServiceSpec(name="persistence",  path="src/framework/port/persistence.py",      layer="service"),
    ServiceSpec(name="authentication", path="src/framework/port/authentication.py", layer="service"),
    ServiceSpec(name="factory",      path="src/framework/service/factory.py",       layer="service"),
]

_FRAMEWORK_MANAGERS = [
    ServiceSpec(name="loader",      path="src/framework/manager/loader.py",      layer="manager", is_class=True),
    ServiceSpec(name="messenger",   path="src/framework/manager/messenger.py",   layer="manager", is_class=True),
    ServiceSpec(name="executor",    path="src/framework/manager/executor.py",    layer="manager", is_class=True),
    ServiceSpec(name="defender",    path="src/framework/manager/defender.py",    layer="manager", is_class=True),
    ServiceSpec(name="tester",      path="src/framework/manager/tester.py",      layer="manager", is_class=True),
    ServiceSpec(name="storekeeper", path="src/framework/manager/storekeeper.py", layer="manager", is_class=True),
    ServiceSpec(name="presenter",   path="src/framework/manager/presenter.py",   layer="manager", is_class=True),
]

# ─────────────────────────────────────────────
# 3. CONTAINER STATO DELL'ARTE (Type-Driven)
# ─────────────────────────────────────────────

class Container:
    def __init__(self):
        self._registry: dict[str | Type, Any] = {}
        self._port_registry: dict[Type, list[Any]] = {}
        self.config: dict[str, Any] = {}
        
        # Inizializzazione cache interne stabili
        self.set("module_cache", {})
        self.set("loading_stack", set())

    def set(self, key: str | Type[T], obj: T) -> None:
        """Registra un singleton usando una stringa o direttamente il Tipo/Interfaccia."""
        self._registry[key] = obj

    def get(self, key: str | Type[T]) -> T:
        """Risolve una dipendenza. Massimo controllo statico se passato un Tipo."""
        if key not in self._registry:
            if isinstance(key, type):
                raise KeyError(f"Nessun provider registrato per l'interfaccia: '{key.__name__}'")
            raise KeyError(f"Chiave '{key}' non trovata nel container")
        
        item = self._registry[key]
        return item() if callable(item) and not inspect.isclass(item) else item

    def has(self, key: str | Type) -> bool:
        return key in self._registry

    def append_to_port(self, interface: Type, obj: Any) -> None:
        """Aggiunge un adapter a un'interfaccia esagonale (Port)."""
        if interface not in self._port_registry:
            self._port_registry[interface] = []
        self._port_registry[interface].append(obj)

    def get_port(self, interface: Type[T]) -> list[T]:
        """Inietta la lista di tutti gli adapter registrati su quel Port."""
        return self._port_registry.get(interface, [])


# ─────────────────────────────────────────────
# 4. CARICATORE DINAMICO E AUTOWIRING BUILDER
# ─────────────────────────────────────────────

class ModuleLoader:
    def __init__(self, container: Container):
        self._container = container

    def load(self, name: str, path: str, inject: dict[str, Any] | None = None) -> Any:
        cache = self._container.get("module_cache")
        if path not in cache:
            cache[path] = self._exec(name, path, inject or {})
        return cache[path]

    @staticmethod
    def _exec(name: str, path: str, inject: dict[str, Any]) -> Any:
        spec = importlib.util.spec_from_file_location(name, path)
        if not spec or not spec.loader:
            raise ImportError(f"Impossibile trovare il modulo {name} in {path}")
        mod = importlib.util.module_from_spec(spec)
        
        for k, v in inject.items(): 
            setattr(mod, k, v)
        spec.loader.exec_module(mod)
        for k, v in inject.items(): 
            setattr(mod, k, v)
            
        return mod

    @staticmethod
    def find_class(mod: Any, name: str) -> Type | None:
        for attr_name in (name, name.capitalize(), 'Adapter', 'adapter'):
            if (cls := getattr(mod, attr_name, None)) is not None:
                return cls
        return None


class AutowiredBuilder:
    """Ispeziona le firme dei costruttori per iniettare dipendenze reali (Zero Stringhe)."""
    def __init__(self, container: Container, module_loader: ModuleLoader):
        self._c = container
        self._ml = module_loader

    async def build(self, spec: ServiceSpec) -> Any:
        # Carica il modulo fisico
        mod = self._ml.load(spec.name, spec.path)
        
        if not spec.is_class:
            # Se è un modulo procedurale, applichiamo la configurazione dizionario nativa
            for k, v in spec.config.items():
                setattr(mod, k, v)
            return mod

        cls = self._ml.find_class(mod, spec.name)
        if cls is None:
            raise ImportError(f"Nessuna classe valida trovata nel file {spec.path}")

        # --- Algoritmo di Autowiring ---
        signature = inspect.signature(cls.__init__)
        kwargs: dict[str, Any] = {}

        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            annotation = param.annotation
            
            # Caso 1: Se il parametro richiede una lista di un Port (Es. `adapters: list[MioPort]`)
            if hasattr(annotation, "__origin__") and annotation.__origin__ is list:
                inner_type = annotation.__args__[0]
                kwargs[param_name] = self._c.get_port(inner_type)
            
            # Caso 2: Se la dipendenza ha un Type Hint registrato nel container (Es. `flow: FlowService`)
            elif annotation is not inspect.Parameter.empty and self._c.has(annotation):
                kwargs[param_name] = self._c.get(annotation)
            
            # Caso 3: Fallback storico su stringhe se l'annotazione combacia con config/nomi spec
            elif self._c.has(param_name):
                kwargs[param_name] = self._c.get(param_name)
                
        # Estende la configurazione manuale passata tramite file (TOML/JSON)
        kwargs.update(spec.config)
        return cls(**kwargs)


# ─────────────────────────────────────────────
# 5. ORCHESTRAZIONE DEL BOOTSTRAP E PARSING
# ─────────────────────────────────────────────

class ProjectLoader:
    def __init__(self, container: Container):
        self._c = container

    def load_schemas(self, directories: list[str]) -> dict[str, Any]:
        raw_data = {}
        for directory in directories:
            if not os.path.exists(directory): continue
            for filename in os.listdir(directory):
                if filename.endswith(".json"):
                    name = os.path.splitext(filename)[0]
                    with open(os.path.join(directory, filename), "r") as f:
                        try:
                            raw_data[name] = json.load(f)
                        except json.JSONDecodeError:
                            continue

        env: Environment = self._c.get('jinja')
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

        return {name: resolve_schema(name) for name in raw_data}

    def parse_specs_from_dict(self, data: dict[str, Any]) -> list[ServiceSpec]:
        """Mappa un file di configurazione in ServiceSpecs dichiarativi."""
        specs = []
        for section, services in data.items():
            if not isinstance(services, dict): 
                continue
                
            for s_name, cfg in services.items():
                # <<< FIX: Se la configurazione non è un dizionario (es. name = "MiaApp"), la saltiamo!
                if not isinstance(cfg, dict):
                    continue
                    
                specs.append(ServiceSpec(
                    name=f"{section.lower()}.{s_name.lower()}",
                    path=f"src/infrastructure/{section}/{cfg.get('adapter')}.py",
                    layer="adapter",
                    is_class=True,
                    is_list=True,
                    config=cfg
                ))
        return specs


class BatchSetup:
    def __init__(self, container: Container, builder: AutowiredBuilder):
        self._c = container
        self._b = builder

    async def run(self, specs: list[ServiceSpec], singletons: dict[str | Type, Any] | None = None) -> list[str]:
        if singletons:
            for k, obj in singletons.items():
                self._c.set(k, obj)

        registry = {s.name: s for s in specs}
        
        # <<< FIX: Mappiamo le dipendenze reali per permettere al TopologicalSorter di fare il suo lavoro
        dep_graph: dict[str, list[str]] = {}
        for s in specs:
            # Uniamo mod_deps e cls_deps (se valorizzati nelle ServiceSpec statiche)
            # Gestiamo sia attributi presenti su dataclass vecchie/nuove usando getattr per sicurezza
            m_deps = getattr(s, 'mod_deps', []) if hasattr(s, 'mod_deps') else []
            c_deps = getattr(s, 'cls_deps', []) if hasattr(s, 'cls_deps') else []
            
            # Filtriamo le dipendenze: teniamo solo quelle che fanno effettivamente parte delle specifiche da caricare
            combined_deps = list(set(m_deps) | set(c_deps))
            dep_graph[s.name] = [d for d in combined_deps if d in registry]

        adapters, managers, services = [], [], []
        
        # Il sorter ora sa che 'flow' deve uscire PRIMA di 'language', 'persistence', ecc.
        sorter = TopologicalSorter(dep_graph)

        for name in sorter.static_order():
            if name not in registry: continue
            spec = registry[name]

            if spec.layer == "adapter": adapters.append(name)
            elif spec.layer == "manager": managers.append(name)
            else: services.append(name)

            try:
                # Se un file fisico non esiste (es. mancano dei file opzionali), stampiamo un warning pulito senza bloccare il resto
                obj = await self._b.build(spec)
                
                if spec.is_list and spec.port_interface:
                    self._c.append_to_port(spec.port_interface, obj)
                else:
                    self._c.set(spec.name, obj)
                    
            except FileNotFoundError as fnf:
                print(f"[-] Componente opzionale saltato (File non trovato): {spec.name} ({fnf.filename})")
                continue
            except Exception as e:
                print(f"[!] Errore instanziazione '{name}': {e}")
                continue

        return managers
# ─────────────────────────────────────────────
# 6. APPLICATION RUNNER (Lifecycle Decoupling)
# ─────────────────────────────────────────────

class Application:
    """Manager del Ciclo di Vita Globale dell'App (Engine agnostico)."""
    def __init__(self, container: Container, manager_names: list[str]):
        self._c = container
        self._managers = manager_names
        self._stop_event = asyncio.Event()
        self._running_tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        print("[*] Avvio dei manager del framework...")
        loop = asyncio.get_running_loop()
        
        # Cattura segnali di terminazione OS
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._stop_event.set)

        for name in self._managers:
            obj = self._c.get(name)
            if isinstance(obj, LifecycleComponent) or hasattr(obj, "start"):
                res = await obj.start()
                if res:
                    if isinstance(res, list):
                        for coro in res: self._running_tasks.append(asyncio.create_task(coro))
                    elif asyncio.iscoroutine(res) or inspect.isawaitable(res):
                        self._running_tasks.append(asyncio.create_task(res))

        print("[+] Framework completamente attivo. In ascolto...")
        await self._stop_event.wait()

    async def stop(self) -> None:
        print("\n[*] Spegnimento controllato dei servizi...")
        for name in reversed(self._managers):
            
            if self._c.has(name):
                obj = self._c.get(name)
                if isinstance(obj, LifecycleComponent) or hasattr(obj, "stop"):
                    await obj.stop()
                
        for task in self._running_tasks:
            if not task.done():
                task.cancel()
                
        print("[*] Framework spento correttamente.")


# ─────────────────────────────────────────────
# 7. FILO DI CONFIGURAZIONE (ENTRY POINT)
# ─────────────────────────────────────────────

class Loader:
    """Orchestratore unico del setup del Container (Fluent Interface)."""
    def __init__(self):
        self.container = Container()
        self._mod_loader = ModuleLoader(self.container)
        self._builder = AutowiredBuilder(self.container, self._mod_loader)
        self._batch = BatchSetup(self.container, self._builder)
        self._project = ProjectLoader(self.container)
        
        self._setup_jinja()

    def _setup_jinja(self) -> None:
        # (Il tuo codice jinja esistente rimane invariato)
        pass

    async def bootstrap(self, config_toml_path: str) -> Application:
        """Inizializza l'intero ecosistema del framework e dell'applicazione."""
        # 1. Forza il setup di Jinja all'inizio del bootstrap sul container corrente
        self._setup_jinja()

        # 2. Carica la configurazione dell'utente (TOML)
        with open(config_toml_path, "rb") as f:
            toml_data = tomli.load(f)
        self.container.config = toml_data

        # 3. Genera le specifiche degli adapter dinamicamente dal TOML
        project_specs = self._project.parse_specs_from_dict(toml_data)
        
        # 4. Carica gli schemi dichiarativi (Ora 'jinja' è sicuramente presente!)
        app_models = self._project.load_schemas(["src/framework/scheme/", "src/application/model/"])
        app_repositories: dict[str, Any] = {}

        # 5. Rimuoviamo il "loader" manager dalle specifiche per evitare il ciclo infinito di build
        # Il loader è già vivo (è 'self'), non deve essere ricostruito dall'AutowiredBuilder!
        filtered_managers = [spec for spec in _FRAMEWORK_MANAGERS if spec.name != "loader"]
        total_specs = _FRAMEWORK_SERVICES + filtered_managers + project_specs
        
        # 6. Avvia l'istanziazione topologica
        managers_to_run = await self._batch.run(
            total_specs,
            singletons={
                "loader": self,
                Container: self.container,
                "models": app_models,
                "repositories": app_repositories
            }
        )
        
        # Aggiungiamo a mano il nome "loader" all'inizio dei manager da eseguire se necessario
        if "loader" not in managers_to_run:
            managers_to_run.insert(0, "loader")
            self.container.set("loader", self) # Mette l'istanza corrente nel container
        
        return Application(self.container, managers_to_run)