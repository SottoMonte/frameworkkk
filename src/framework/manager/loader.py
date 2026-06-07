import os
import sys
import importlib.util
import asyncio
import signal
import inspect
import traceback
import json
import uuid
import ast
from dataclasses import dataclass, field
from typing import Type, TypeVar, Any, Protocol, runtime_checkable, Callable
import types
from graphlib import TopologicalSorter
from jinja2 import Environment, BaseLoader
import tomli
from dependency_injector import containers, providers

# ─────────────────────────────────────────────
# 3. CONTAINER DI (dependency-injector)
# ─────────────────────────────────────────────

T = TypeVar('T')

class ContainerWrapper:
    """DI Container minimalista senza wrapper superflui."""
    
    class _DIContainer(containers.DeclarativeContainer):
        config = providers.Configuration()
        module_cache = providers.Singleton(dict)
        loading_stack = providers.Singleton(set)
        jinja = providers.Singleton(lambda: Environment(loader=BaseLoader()))
    
    def __init__(self):
        self._di = self._DIContainer()
        self._ports: dict[Type, list[Any]] = {}
    
    def set(self, key: str | Type[T], obj: T) -> None:
        """Registra un singleton nel container."""
        key_str = key if isinstance(key, str) else key.__name__
        setattr(self._di, key_str, providers.Singleton(lambda o=obj: o))
    
    def get(self, key: str | Type[T]) -> T:
        """Risolve una dipendenza dal container."""
        key_str = key if isinstance(key, str) else key.__name__
        attr = getattr(self._di, key_str, None)
        if attr is None:
            raise KeyError(f"Chiave '{key_str}' non trovata nel container")
        if isinstance(attr, providers.Provider):
            return attr()
        return attr
    
    def has(self, key: str | Type) -> bool:
        """Verifica se una chiave è registrata."""
        key_str = key if isinstance(key, str) else key.__name__
        return hasattr(self._di, key_str)
    
    def append_to_port(self, interface: Type, obj: Any) -> None:
        """Aggiunge un adapter a un Port."""
        if interface not in self._ports:
            self._ports[interface] = []
        self._ports[interface].append(obj)

    def get_port(self, interface: Type[T]) -> list[T]:
        """Inietta tutti gli adapter su un Port."""
        return self._ports.get(interface, [])

class AutowiredBuilder:
    """Ispeziona le firme dei costruttori per iniettare dipendenze reali usando dependency-injector."""

    async def build(self, spec) -> Any:
        # Prepare an inject dict con i servizi già registrati nel container
        inject: dict[str, Any] = {}
        try:
            # Itera su tutti gli attributi del Container
            for attr_name in dir(self._c._di):
                if attr_name.startswith('_'):
                    continue
                attr = getattr(self._c._di, attr_name)
                if isinstance(attr, providers.Provider):
                    try:
                        inject[attr_name] = attr()
                    except Exception:
                        pass
        except Exception:
            inject = {}

        # Carica i Port (es. MessagePort) e aggiunge le loro symbols all'inject
        try:
            ports_dir = os.path.join("src", "framework", "port")
            if os.path.isdir(ports_dir):
                for fname in os.listdir(ports_dir):
                    if not fname.endswith('.py'):
                        continue
                    ppath = os.path.join(ports_dir, fname)
                    try:
                        pmod = self._ml.load(f"port.{os.path.splitext(fname)[0]}", ppath, inject=inject)
                        for attr_name, attr_val in vars(pmod).items():
                            if not attr_name.startswith("_") and attr_name not in inject:
                                inject[attr_name] = attr_val
                    except Exception:
                        continue
        except Exception:
            pass

        mod = self._ml.load(spec.name, spec.path, inject=inject)
        
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

            # Caso speciale: se il costruttore accetta **kwargs, passiamo tutte
            # le entry registrate nel container come defaults.
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                try:
                    for attr_name in dir(self._c._di):
                        if attr_name.startswith('_') or attr_name in kwargs:
                            continue
                        attr = getattr(self._c._di, attr_name)
                        if isinstance(attr, providers.Provider):
                            try:
                                kwargs[attr_name] = attr()
                            except Exception:
                                pass
                except Exception:
                    pass
                continue
            
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
# 7. FILO DI CONFIGURAZIONE (ENTRY POINT)
# ─────────────────────────────────────────────

class Loader:
    services: dict[str, Any] = {
        'flow': 'src/framework/service/flow.py'
    }


    """Orchestratore unico del setup del Container (Fluent Interface + dependency-injector)."""
    def __init__(self):
        # Instanzia il Container
        self.container = ContainerWrapper()
        
        # Inizializza cache
        #self.container._di.module_cache.override({})
        #self.container._di.loading_stack.override(set())
        
        '''self._mod_loader = ModuleLoader(self.container)
        self._builder = AutowiredBuilder(self.container, self._mod_loader)
        self._batch = BatchSetup(self.container, self._builder)
        self._project = ProjectLoader(self.container)'''

    async def string_to_module(self, module_code: str, module_name: str = "dynamic_module") -> types.ModuleType:
        """
        Prende una stringa contenente codice Python e la compila 
        restituendo un oggetto modulo Python 3 pronto all'uso.
        """
        # 1. Crea un oggetto modulo vuoto con il nome specificato
        mod = types.ModuleType(module_name)
        
        # 2. (Opzionale ma consigliato) Registra il modulo nel sistema sys.modules
        # Questo permette al modulo di gestire correttamente eventuali import interni
        sys.modules[module_name] = mod
        
        try:
            # 3. Esegue il codice della stringa all'interno del dizionario del nuovo modulo
            # exec() popolerà il namespace del modulo con funzioni, classi e variabili
            exec(module_code, mod.__dict__)
        except Exception as e:
            # Rimuove il modulo da sys.modules in caso di errore per non lasciare rimasugli
            del sys.modules[module_name]
            raise e
            
        return mod

    async def estrai_imports(self, codice_sorgente: str) -> list:
        """
        Analizza una stringa di codice Python ed estrae tutti i moduli importati.
        Gestisce sia 'import modulo' che 'from modulo import sottomodulo'.
        """
        moduli_importati = []
        
        try:
            # Trasforma il codice in un Albero della Sintassi Astratta (AST)
            albero = ast.parse(codice_sorgente)
        except SyntaxError as e:
            print(f"Errore di sintassi nel codice fornito: {e}")
            return moduli_importati

        # Cammina attraverso tutti i nodi del codice
        for nodo in ast.walk(albero):
            # Caso 1: import classico (es. import os, sys)
            if isinstance(nodo, ast.Import):
                for nome in nodo.names:
                    moduli_importati.append(nome.name)
                    
            # Caso 2: import dal costrutto 'from' (es. from math import pi)
            elif isinstance(nodo, ast.ImportFrom):
                if nodo.module:  # Gestisce il caso in cui il modulo non sia None
                    moduli_importati.append(nodo.module)
                    
        # Rimuove i duplicati mantenendo l'ordine di apparizione
        return list(dict.fromkeys(moduli_importati))

    async def bootstrap(self, config_toml_path: str):

        # 2. Carica la configurazione dell'utente (TOML)
        with open(config_toml_path, "rb") as f:
            toml_data = tomli.load(f)