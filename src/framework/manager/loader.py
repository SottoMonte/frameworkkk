import os
import importlib.util
import asyncio
from graphlib import TopologicalSorter
from dependency_injector import containers, providers
import tomli
import signal

class Container(containers.DynamicContainer):
    config = providers.Configuration()
    module_cache = providers.Singleton(dict)
    loading_stack = providers.Singleton(set)
    # Definiamo i ports come mappe di provider o liste
    presentations = providers.Singleton(list,[])
    persistences = providers.Singleton(list,[])
    messages = providers.Singleton(list,[])
    authentications = providers.Singleton(list,[])
    actuators = providers.Singleton(list,[])
    authorizations = providers.Singleton(list,[])

class loader:
    def __init__(self, **config):
        self.config = config
        self.container = Container()
        # Lista ufficiale dei port supportati
        self.valid_ports = ["presentation", "persistence", "message", "authentication", "actuator", "authorization"]
        self.ports_class_deps = {
            "presentation": ["defender","messenger"],
            "persistence": ["executor"],
            "message": ["storekeeper","messenger"],
            "authentication": [],
            "actuator": [],
            "authorization": []
        }


    def _create_mod(self, name, path):
        """Crea il modulo senza eseguirlo (per permettere l'iniezione pre-exec)."""
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        return spec, mod

    def _get_mod(self, name, path, pre_inject=None):
        cache = self.container.module_cache()
        if path not in cache:
            spec, mod = self._create_mod(name, path)
            # Inietta le dipendenze PRIMA di exec_module
            for k, v in (pre_inject or {}).items():
                setattr(mod, k, v)
            spec.loader.exec_module(mod)
            cache[path] = mod
        return cache[path]

    async def _build(self, spec: dict):
        name, path = spec["name"], spec["path"]

        # --- 1. Risoluzione dipendenze del MODULO (Globali) ---
        mod_args = {}
        for d in spec.get("mod_deps", []):
            mod_args[d] = await self.get(d)

        # --- 2. Risoluzione dipendenze della CLASSE (Costruttore) ---
        cls_args = {}
        for d in spec.get("cls_deps", []):
            if d in self.valid_ports:
                cls_args[d] = getattr(self.container, d)
            else:
                cls_args[d] = await self.get(d)

        # Uniamo i parametri di configurazione a quelli della classe
        constructor_args = {**cls_args, **spec.get("config", {})}

        if spec.get("is_class"):
            # Carica il modulo iniettando le sue dipendenze globali (se presenti)
            mod = self._get_mod(name, path, pre_inject=mod_args)
            
            # Trova la classe nel modulo
            cls = next((v for v in vars(mod).values() 
                        if isinstance(v, type) and v.__module__ == mod.__name__), None)
            
            if not cls:
                raise ImportError(f"Nessuna classe trovata in {path}")
                
            return cls(**constructor_args)

        # Se è un semplice modulo, iniettiamo tutto (mod_deps + config) come globali
        full_mod_args = {**mod_args, **spec.get("config", {})}
        mod = self._get_mod(name, path, pre_inject=full_mod_args)
        
        # Aggiornamento post-exec per sicurezza
        for k, v in full_mod_args.items():
            setattr(mod, k, v)
            
        return mod

    async def _setup_batch(self, specs: list[dict]):
        registry = {s["name"]: s for s in specs}
        # Uniamo mod_deps e cls_deps per il calcolo del grafo
        dep_graph = {}
        for s in specs:
            all_deps = set(s.get("mod_deps", [])) | set(s.get("cls_deps", []))
            dep_graph[s["name"]] = list(all_deps)

        sorter = TopologicalSorter(dep_graph)
        
        # Inizializza le liste dei port nel container se non esistono
        for p in self.valid_ports:
            if not hasattr(self.container, p):
                setattr(self.container, p, [])

        for name in sorter.static_order():
            if name in registry:
                spec = registry[name]
                
                # Istanziazione
                if name == "container":
                    obj = self.container
                elif name == "loader":
                    obj = self
                else:
                    obj = await self._build(spec)

                # 1. Registrazione per nome univoco
                if spec.get("is_list",False):
                    port_list = getattr(self.container, spec.get("port"),None)
                    lista = port_list()
                    lista.append(obj)
                    #print(f"[*] Classe '{name}' registrato nel port '{spec.get('port')}'")
                else:
                    setattr(self.container, name, providers.Singleton(any,obj))
                    
    async def get(self, name: str, spec: dict = None) -> any:
        if hasattr(self.container, name):
            return getattr(self.container, name)
        
        # Se chiedi un port intero che non è ancora stato popolato ma è valido
        if name in self.valid_ports:
            return getattr(self.container, name)

        stack = self.container.loading_stack()
        if name in stack:
            raise RecursionError(f"Ciclo rilevato: {name}")

        if not spec:
            raise KeyError(f"Specifica mancante per {name}")

        stack.add(name)
        try:
            obj = await self._build(spec)
            setattr(self.container, name, obj)
            return obj
        finally:
            stack.remove(name)

    def get_sync(self, name) -> any:
        if hasattr(self.container, name):
            return getattr(self.container, name)()
        else:
            raise KeyError(f"Servizio '{name}' non trovato")

    def read_config(self,file_path):
        """
        Legge un file TOML e restituisce un dizionario.
        Gestisce l'assenza del file con un errore descrittivo.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configurazione non trovata: {file_path}")
        
        try:
            with open(file_path, "rb") as f:
                return tomli.load(f)
        except Exception as e:
            raise RuntimeError(f"Errore nel parsing del file {file_path}: {e}")

    def resource(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Risorsa non trovata: {path}")
        
        if path.endswith(".py"):
            cache = self.container.module_cache()
            if path not in cache:
                name = os.path.splitext(os.path.basename(path))[0]
                spec, mod = self._create_mod(name, path)
                spec.loader.exec_module(mod)
                cache[path] = mod
            return cache[path]
        
        try:
            with open(path, "r") as f:
                return f.read()
        except Exception as e:
            raise RuntimeError(f"Errore nel parsing del file {path}: {e}")

    async def load_project(self, main_config_path: str):
        # 1. Carica il file principale
        project_data = self.read_config(main_config_path)
        
        # Inietta la configurazione globale nel container
        self.container.config.from_dict(project_data)
        
        #policies = project_data.get("project", {}).get("policy", {})
        services = project_data
        specs = []

        # 2. Cicla sui Port definiti nelle policy
        for port_name, services in project_data.items():
            if port_name not in self.valid_ports:
                continue
            for service_name, config_file in services.items():
                adapter = config_file.get("adapter")
                print(f"[*] Port: {port_name}.{adapter} in {port_name}s")
            
                # 3. Crea la specifica dinamica
                spec = {
                    "name": "Adapter",
                    "path": f"src/infrastructure/{port_name}/{adapter}.py",
                    "mod_deps": [port_name],
                    "cls_deps": self.ports_class_deps[port_name],
                    "port": port_name+"s",
                    "is_class": True, # Di solito i backend sono classi
                    "is_list": True,
                    "config": config_file
                }
                #print(f"[*] Spec: {spec}")
                specs.append(spec)

        # 4. Avvia il caricamento batch
        #await self._setup_batch(specs)
        #return project_data
        return specs

    async def bootstrap(self,args):
        services = [
            {"name": "container", "path": "src/framework/service/container.py", "mod_deps": [], "is_class": False, "config": {}},
            {"name": "scheme", "path": "src/framework/service/scheme.py", "mod_deps": [], "is_class": False, "config": {}},
            {"name": "flow", "path": "src/framework/service/flow.py", "mod_deps": ["scheme","loader"], "is_class": False, "config": {}},
            {"name": "language", "path": "src/framework/service/language.py", "mod_deps": ["scheme", "flow"], "is_class": False, "config": {}},
            {"name": "diagnostic", "path": "src/framework/service/diagnostic.py", "mod_deps": ["scheme", "flow"], "is_class": False, "config": {}},
            {"name": "message", "path": "src/framework/port/message.py", "mod_deps": [], "is_class": False, "config": {}},
            {"name": "presentation", "path": "src/framework/port/presentation.py", "mod_deps": [], "is_class": False, "config": {}},
            {"name": "persistence", "path": "src/framework/port/persistence.py", "mod_deps": [], "is_class": False, "config": {}},
        ]

        managers = [
            {"name": "loader", "path": "src/framework/manager/loader.py", "mod_deps": ["container"], "is_class": True, "config": {}},
            {"name": "messenger", "path": "src/framework/manager/messenger.py", "mod_deps": ["flow"],"cls_deps": ["executor","message"], "is_class": True, "config": {}},
            {"name": "executor", "path": "src/framework/manager/executor.py", "mod_deps": ["flow"], "cls_deps": ["defender","language"], "is_class": True, "config": {'args':args}},
            {"name": "defender", "path": "src/framework/manager/defender.py", "mod_deps": ["flow"], "cls_deps": [], "is_class": True, "config": {'args':args}},
            {"name": "tester", "path": "src/framework/manager/tester.py", "mod_deps": ["language","flow","diagnostic"], "cls_deps": ["loader"], "is_class": True, "config": {'args':args}},
            {"name": "storekeeper", "path": "src/framework/manager/storekeeper.py", "mod_deps": [], "cls_deps": ["executor","persistences"], "is_class": True, "config": {}},
            # {"name": "sensor", "path": "src/framework/manager/sensor.py", "deps": ["container"], "is_class": True, "config": {}},
            {"name": "presenter", "path": "src/framework/manager/presenter.py", "mod_deps": [], "cls_deps": ["executor","presentations"], "is_class": True, "config": {}},
            # {"name": "inferencer", "path": "src/framework/manager/inferencer.py", "deps": ["container"], "is_class": True, "config": {}},
            # {"name": "actuator", "path": "src/framework/manager/actuator.py", "deps": ["container"], "is_class": True, "config": {}},
        ]

        specs = await self.load_project("pyproject.toml")
        await self._setup_batch(services+managers+specs)

        self._stop_event = asyncio.Event()

        print("[*] Framework bootstrapped. Running...") 

        def handle_exit():
            print("\n[!] Shutdown richiesto.")
            self._stop_event.set()

        # Registra il segnale Ctrl+C (SIGINT)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_exit)

        try:
            # Avvia i manager che hanno un lifecycle
            for manager in managers:
                obj = self.get_sync(manager["name"])
                if hasattr(obj, "start"):
                    await obj.start()
            await self._stop_event.wait()

        except Exception as e:
            print(f"[!] Framework spento con errore: {e}")
        finally:
            for manager in managers:
                obj = self.get_sync(manager["name"])
                print(obj)
                if hasattr(obj, "stop"):
                    await obj.stop()
            print("[*] Framework spento correttamente.")