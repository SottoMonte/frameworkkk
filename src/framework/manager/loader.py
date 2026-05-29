import os
import json
import uuid
import asyncio
import signal
import importlib.util
from graphlib import TopologicalSorter

# Nota: Dal 2026 (Python 3.11+), tomllib è nativo nella Standard Library.
# Usiamo il fallback su tomli solo per retrocompatibilità.
try:
    import tomllib
except ImportError:
    import tomli as tomllib

from jinja2 import Environment, BaseLoader


# ─────────────────────────────────────────────────────────────
# 1. CORE CONTAINER (Iniezione delle dipendenze nativa)
# ─────────────────────────────────────────────────────────────
class TinyContainer:
    """Registro centrale per l'Iniezione delle Dipendenze e la gestione delle Porte."""
    def __init__(self):
        self._registry = {}
        self._ports = {}

    def set(self, name: str, obj): 
        self._registry[name] = obj

    def get(self, name: str):
        if name not in self._registry: 
            raise KeyError(f"Componente '{name}' non registrato nel container.")
        return self._registry[name]

    def has(self, name: str) -> bool:
        return name in self._registry

    def register_to_port(self, port: str, adapter):
        """Registra un adapter in una specifica porta esagonale (es. 'persistence')."""
        if port not in self._ports: 
            self._ports[port] = []
        self._ports[port].append(adapter)
        # Sincronizza automaticamente la collezione al plurale (es. "persistences")
        self.set(f"{port}s", self._ports[port])


# ─────────────────────────────────────────────────────────────
# 2. SATELLITE ENGINE: JSON & JINJA2 (Gestione Schemi)
# ─────────────────────────────────────────────────────────────
class JinjaJsonEngine:
    """Isola il caricamento, la risoluzione dinamica tramite Jinja2 e il parsing dei JSON."""
    def __init__(self, container: TinyContainer):
        self._c = container
        self.env = Environment(loader=BaseLoader())
        
        # Configurazione filtri e globali nativi di Jinja
        self.env.filters['tojson'] = lambda obj: json.dumps(obj)
        self.env.globals['uuid4'] = lambda: str(uuid.uuid4())
        self.env.filters['get'] = lambda d, k, df=None: (
            self._c.get('models').get(d, {}).get(k, df) if self._c.has('models') else d.get(k, df)
        )
        self._c.set('jinja', self.env)

    def load_schemas(self, directories: list[str]) -> dict:
        raw_data = {}
        for directory in filter(os.path.exists, directories):
            for filename in filter(lambda f: f.endswith(".json"), os.listdir(directory)):
                name = os.path.splitext(filename)[0]
                with open(os.path.join(directory, filename), "r", encoding="utf-8") as f:
                    raw_data[name] = json.load(f)

        cache = {}
        def resolve(name):
            if name in cache and cache[name]: 
                return cache[name]
            raw_obj = raw_data.get(name)
            if not raw_obj: 
                return None
            cache[name] = {} 

            def _parse(val):
                if isinstance(val, dict): 
                    return {k: _parse(v) for k, v in val.items()}
                if isinstance(val, list): 
                    return [_parse(i) for i in val]
                if isinstance(val, str) and "{{" in val:
                    stripped = val.strip()
                    if stripped.startswith("{{") and stripped.endswith("}}") and "|" not in stripped:
                        ref = stripped[2:-2].strip()
                        if ref in raw_data: 
                            return resolve(ref)
                        if ref in self.env.globals:
                            g = self.env.globals[ref]
                            return g() if callable(g) else g
                    
                    ctx = {**self.env.globals, **raw_data, **{k: v for k, v in cache.items() if v}}
                    return self.env.from_string(val).render(**ctx)
                return val

            cache[name] = _parse(raw_obj)
            return cache[name]

        final_schemas = {name: resolve(name) for name in raw_data}
        
        # Supporto opzionale e isolato per il registro Cerberus
        try:
            from cerberus import schema_registry
            for name, sc in final_schemas.items():
                try: 
                    schema_registry.add(name, sc)
                except: 
                    pass
        except ImportError: 
            pass

        return final_schemas


# ─────────────────────────────────────────────────────────────
# 3. SATELLITE ENGINE: DSL & INTERPRETER (Logica Dinamica)
# ─────────────────────────────────────────────────────────────
class DslRepositoryEngine:
    """Isola l'esecuzione dei file .dsl e la gestione delle sessioni isolate."""
    def __init__(self, container: TinyContainer):
        self._c = container

    async def load_repositories(self, directories: list[str]) -> dict:
        raw_data = {}
        if not (self._c.has("interpreter") and self._c.has("language")):
            print("[!] Componenti 'interpreter' o 'language' non trovati. DSL caricato come testo statico.")
            return raw_data

        interpreter = self._c.get("interpreter")
        language = self._c.get("language")
        await interpreter.create_session("loader_repositories", language.DSL_FUNCTIONS)

        for directory in filter(os.path.exists, directories):
            for filename in filter(lambda f: f.endswith(".dsl"), os.listdir(directory)):
                name = os.path.splitext(filename)[0]
                with open(os.path.join(directory, filename), "r", encoding="utf-8") as f:
                    content = f.read()
                    file_path = f"application/repository/{name}.py"
                    
                    await interpreter.add_file(file_path, content)
                    res = await interpreter.run_session("loader_repositories", file_path)
                    raw_data[name] = res.get('repository', res) if isinstance(res, dict) else res
        return raw_data


# ─────────────────────────────────────────────────────────────
# 4. COMPONENT ORCHESTRATOR (Algoritmo, Sort & Istanziazione)
# ─────────────────────────────────────────────────────────────
class ComponentOrchestrator:
    """Ha la responsabilità esclusiva di risolvere l'ordine dei componenti e istanziarli."""
    def __init__(self, container: TinyContainer):
        self._c = container

    def _load_module(self, name: str, path: str, inject: dict):
        """Esegue il caricamento fisico del file Python ed effettua l'iniezione sicura."""
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        
        for k, v in inject.items(): 
            setattr(mod, k, v)
        spec.loader.exec_module(mod)
        for k, v in inject.items(): 
            setattr(mod, k, v) # Doppia iniezione di sicurezza a livello di modulo
            
        return getattr(mod, name.capitalize(), getattr(mod, "Adapter", mod))

    def _prepare_specs(self, config: dict) -> tuple[dict, dict]:
        """Elabora la configurazione ignorando i metadati e mappando solo i veri adapter."""
        specs, dep_graph = {}, {}
        
        # Elenco delle sezioni di configurazione globale da NON trattare come Porte
        SEZIONI_GLOBALI = {"project", "tool"} 

        for port, providers in config.items():
            # 1. Salta il blocco 'project' o configurazioni non-dizionario
            if port in SEZIONI_GLOBALI or not isinstance(providers, dict):
                continue
                
            for provider, cfg in providers.items():
                # 2. Controllo difensivo: se il provider non è un dizionario, ignoralo
                if not isinstance(cfg, dict):
                    continue
                
                # 3. Verifica che ci sia l'attributo essenziale 'adapter'
                if "adapter" not in cfg:
                    continue

                name = f"{port}.{provider}"
                deps = cfg.get("deps", [])
                
                specs[name] = {
                    "path": f"src/infrastructure/{port}/{cfg['adapter']}.py",
                    "port": port, 
                    "cfg": cfg, 
                    "deps": deps, 
                    "name": provider
                }
                dep_graph[name] = deps
                
        return specs, dep_graph

    async def resolve_and_build(self, config: dict):
        """Risolve l'ordine topologico e costruisce l'albero infrastrutturale."""
        specs, dep_graph = self._prepare_specs(config)
        
        # Risoluzione del grafo isolata in questo modulo (Rimosso dal Bootstrap)
        for name in TopologicalSorter(dep_graph).static_order():
            if name not in specs: 
                continue
            spec = specs[name]

            # Risoluzione automatica delle dipendenze richieste tramite il container
            inject = {dep: self._c.get(dep) for dep in spec["deps"] if self._c.has(dep)}
            
            # Caricamento dinamico
            obj_cls = self._load_module(spec["name"], spec["path"], inject)
            instance = obj_cls(**spec["cfg"]) if isinstance(obj_cls, type) else obj_cls

            # Registrazione nel container e mappatura porte
            self._c.set(name, instance)
            self._c.register_to_port(spec["port"], instance)

            # Esecuzione asincrona dei cicli di vita dei singoli adattatori (es. Server HTTP)
            if hasattr(instance, "start") and asyncio.iscoroutinefunction(instance.start):
                asyncio.create_task(instance.start())
                print(f"[+] Componente avviato in background: {name}")


# ─────────────────────────────────────────────────────────────
# 5. CORE FRAMEWORK (Il Direttore d'Orchestra)
# ─────────────────────────────────────────────────────────────
class Loader:
    """Punto d'ingresso principale dell'applicazione. Descrive SOLO la sequenza di avvio."""
    def __init__(self):
        self.container = TinyContainer()
        self.container.set("framework", self)
        
        # Composizione dei moduli satellite specialistici
        self.schema_engine = JinjaJsonEngine(self.container)
        self.dsl_engine = DslRepositoryEngine(self.container)
        self.orchestrator = ComponentOrchestrator(self.container)

    def _read_config(self, path: str) -> dict:
        with open(path, "rb") as f: 
            return tomllib.load(f)

    async def _handle_graceful_shutdown(self):
        """Gestisce i segnali POSIX del sistema operativo per lo spegnimento controllato."""
        stop_event = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, stop_event.set)
        
        print("[+] Framework pronto e in ascolto.")
        await stop_event.wait()
        
        print("\n[!] Segnale di terminazione intercettato. Spegnimento dei servizi...")
        for name, instance in self.container._registry.items():
            if hasattr(instance, "stop") and asyncio.iscoroutinefunction(instance.stop):
                await instance.stop()
                print(f"[-] Componente spento: {name}")
        print("[*] Framework arrestato con successo.")

    # ─────────────────────────────────────────────────────────────
    # IL BOOTSTRAP DICHIARATIVO
    # ─────────────────────────────────────────────────────────────
    async def bootstrap(self, args=[]):
        """Avvia l'applicazione seguendo rigorosamente le macro-fasi logiche."""
        print("[*] Inizio procedura di Bootstrap...")
        
        # 1. Caricamento della configurazione statica
        config = self._read_config("./pyproject.toml")

        print(config)

        # 2. Fase Schemi: Caricamento e rendering Jinja2 dei modelli JSON
        app_models = self.schema_engine.load_schemas(["src/framework/scheme/", "src/application/model/"])
        self.container.set("models", app_models)
        self.container.set("repositories", {}) # Inizializzazione contenitore repository

        # 3. Fase Infrastruttura: Risoluzione del grafo di dipendenze e istanziazione
        await self.orchestrator.resolve_and_build(config)
        
        # 4. Fase DSL: Caricamento dinamico dei repository tramite l'interprete pronto
        loaded_repos = await self.dsl_engine.load_repositories(["src/application/repository/"])
        self.container.get("repositories").update(loaded_repos)
        
        # 5. Fase di runtime: Passaggio del controllo al ciclo di vita del sistema operativo
        await self._handle_graceful_shutdown()