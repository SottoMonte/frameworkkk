import os
import sys
import importlib.util
import asyncio
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
        if not isinstance(key, str):
            if key in self._ports:
                return self._ports[key]
            if hasattr(key, "__name__"):
                key = key.__name__
            else:
                #print(dir(key),key)
                return None
            

        attr = getattr(self._di, key, None)
        if isinstance(attr, providers.Provider):
            return attr()
        return attr
    
    def has(self, key: str | Type) -> bool:
        """Verifica se una chiave è registrata."""
        if not isinstance(key, str):
            if key in self._ports:
                return True
            if hasattr(key, "__name__"):
                key = key.__name__
            else:
                return False
        return hasattr(self._di, key)
    
    def append_to_port(self, interface: Type, obj: Any) -> None:
        """Aggiunge un adapter a un Port."""
        if interface not in self._ports:
            self._ports[interface] = []
        self._ports[interface].append(obj)

    def get_port(self, interface: Type[T]) -> list[T]:
        """Inietta tutti gli adapter su un Port."""
        return self._ports.get(interface, [])


# ─────────────────────────────────────────────
# 7. FILO DI CONFIGURAZIONE (ENTRY POINT)
# ─────────────────────────────────────────────

class Loader:
    services: dict[str, Any] = {
        'flow': 'src/framework/service/flow.py',
        'factory': 'src/framework/service/factory.py',
        'language': 'src/framework/service/language.py',
        'scheme': 'src/framework/service/scheme.py',
        'manage': 'src/framework/port/manage.py',
    }

    ports: dict[str, Any] = {
        'message': 'src/framework/port/message.py',
        'presentation': 'src/framework/port/presentation.py',
        'persistence': 'src/framework/port/persistence.py',
    }

    managers: dict[str, Any] = {
        'messenger': 'src/framework/manager/messenger.py',
        'storekeeper': 'src/framework/manager/storekeeper.py',
        #'presenter': 'src/framework/manager/presenter.py',
        #'defender': 'src/framework/manager/defender.py',
        #'orchestrator': 'src/framework/manager/orchestrator.py',
    }




    """Orchestratore unico del setup del Container (Fluent Interface + dependency-injector)."""
    def __init__(self):
        # Instanzia il Container
        self.container = ContainerWrapper()
        self.container.set(Loader, self)  # Placeholder per la factory, sarà sovrascritta dopo il bootstrap

    def _ensure_package(self, package_name: str) -> types.ModuleType:
        """Crea i package intermedi necessari per i moduli framework.*."""
        if package_name in sys.modules:
            return sys.modules[package_name]

        pkg = types.ModuleType(package_name)
        pkg.__path__ = []
        pkg.__package__ = package_name.rpartition('.')[0]
        pkg.__spec__ = importlib.util.spec_from_loader(package_name, loader=None)
        pkg.__loader__ = None

        sys.modules[package_name] = pkg

        if '.' in package_name:
            parent_name, child_name = package_name.rsplit('.', 1)
            parent_pkg = self._ensure_package(parent_name)
            setattr(parent_pkg, child_name, pkg)

        return pkg

    def _register_module(self, module_name: str, module: types.ModuleType) -> None:
        """Registra il modulo e i relativi alias nel package framework."""
        sys.modules[module_name] = module

        if '.' in module_name:
            package_name, short_name = module_name.rsplit('.', 1)
            parent_pkg = self._ensure_package(package_name)
            setattr(parent_pkg, short_name, module)

        self.container.set(module_name, module)

    async def string_to_module(self, module_code: str, module_name: str, module_path: str) -> types.ModuleType:
        """
        Compila una stringa di codice Python in un modulo.
        Le dipendenze devono essere già caricate in sys.modules.
        """
        if '.' in module_name:
            package_name = module_name.rpartition('.')[0]
            self._ensure_package(package_name)

        mod = types.ModuleType(module_name)
        mod.__file__ = module_path
        mod.__package__ = module_name.rpartition('.')[0]
        mod.__spec__ = importlib.util.spec_from_loader(module_name, loader=None)
        mod.__loader__ = None
        
        self._register_module(module_name, mod)
        
        try:
            if module_name == "framework.service.scheme":
                mod.__dict__["schemes"] = self.container.get("schemes")
            exec(module_code, mod.__dict__)
        except Exception as e:
            del sys.modules[module_name]
            print(f"Errore durante il caricamento del modulo '{module_name}' da '{module_path}': {e}")
            raise e
        
        print(f"[+] Modulo '{module_name}' caricato da '{module_path}'")
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

    async def read(self, path: str) -> str:
        """Legge il contenuto di un file."""
        with open(path, "rb") as f:
            return f.read().decode()

    async def load_schemes(self, directories: list[str]) -> dict:
        raw_data = {}

        for directory in directories:
            if not os.path.exists(directory):
                continue

            for filename in os.listdir(directory):
                if filename.endswith(".json"):
                    name = os.path.splitext(filename)[0]
                    with open(os.path.join(directory, filename), "r", encoding="utf-8") as f:
                        try:
                            raw_data[name] = json.load(f)
                        except json.JSONDecodeError as e:
                            print(f"[!] Errore sintassi JSON in {filename}: {e}")
                            continue

        env = Environment(loader=BaseLoader())
        if 'tojson' not in env.filters:
            env.filters['tojson'] = lambda obj: json.dumps(obj)
        env.globals['uuid4'] = lambda: str(uuid.uuid4())

        cache = {}
        def resolve_schema(name):
            if name in cache:
                return cache[name]

            raw_obj = raw_data.get(name)
            if raw_obj is None:
                return None

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

        final_schemas = {}
        for name in raw_data:
            final_schemas[name] = resolve_schema(name)

        if final_schemas:
            print(f"[+] Schemi caricati: {', '.join(sorted(final_schemas.keys()))}")
        else:
            print("[!] Nessuno schema caricato: directory vuota o file JSON non validi")

        try:
            from cerberus import schema_registry
            for name, schema in final_schemas.items():
                try:
                    schema_registry.add(name, schema)
                except Exception:
                    pass
        except ImportError:
            pass

        return final_schemas

    async def _get_module_dependencies(self, module_code: str) -> set[str]:
        """Estrae le dipendenze da altri moduli framework."""
        imports = await self.estrai_imports(module_code)
        normalized = [imp.split('.')[-1] for imp in imports]
        return {imp for imp in normalized if imp in self.services or imp in self.ports}

    async def _load_in_order(self):
        """Carica i moduli ordinati topologicamente in base alle dipendenze."""
        # Costruisci il grafo delle dipendenze
        dependencies = {}
        module_codes = {}
        
        carica = self.services | self.ports
        for name, path in carica.items():
            qualified_name = f"framework.service.{name}" if name in self.services else f"framework.port.{name}"
            if qualified_name in sys.modules:
                continue
            code = await self.read(path)
            module_codes[name] = (code, path)
            dependencies[name] = await self._get_module_dependencies(code)
        
        # Ordina topologicamente e carica
        if dependencies:
            sorter = TopologicalSorter(dependencies)
            for module_name in sorter.static_order():
                if module_name in module_codes:
                    code, path = module_codes[module_name]
                    qualified_name = f"framework.service.{module_name}" if module_name in self.services else f"framework.port.{module_name}"
                    await self.string_to_module(code, qualified_name, path)

    async def _load_level(self,name,config,key,path):
        adapter_path = path
        if os.path.isfile(adapter_path):
            code = await self.read(adapter_path)
            module = await self.string_to_module(code, name, adapter_path)
            adapter_class = getattr(module, 'Manager' if key == 'Managers' else 'Adapter', None)
            signature = inspect.signature(adapter_class.__init__)
            ok = [param.annotation.__args__[0] if hasattr(param.annotation, "__origin__") and param.annotation.__origin__ is list else param.annotation for param_name, param in signature.parameters.items() if param_name != 'self' and param.annotation is not inspect._empty ]
            match key:
                case 'Managers':
                    
                    #print("---->",name,key,ok)
                    args = [self.container.get(param) for param in ok]
                    instance = adapter_class(*args, **config)
                    self.container.set(adapter_class, instance)
                    print(f"[+] Manager '{name}' caricato e registrato come singleton")
                case _:
                    
                    #print("---->",name,key,getattr(module, key).Port,dir(module))
                    instance = adapter_class(**config)
                    self.container.append_to_port(getattr(module, key).Port, instance)
                    print(f"[+] Adapter '{name}' in {key}s caricato e registrato per il Port '{key}'")
            return instance
        else:
            print(f"Attenzione: File dell'adapter '{name}' non trovato in '{adapter_path}'")

    async def bootstrap(self, config_toml_path: str):
        """Avvia il framework caricando i moduli in ordine di dipendenze."""
        schemes = await self.load_schemes(["src/framework/scheme", "src/application/model"])
        self.container.set('schemes', schemes)
        
        await self._load_in_order()
        
        config = await self.read(config_toml_path)
        config_data = tomli.loads(config)
        #print(f"[+] Configurazione caricata da '{config_data}'")

        for key in self.ports.keys():
            if key in config_data:
                adapters = config_data[key]
                for i,adapter_name in enumerate(adapters):
                    adapter_config = adapters[adapter_name]
                    adapter_path = f"src/infrastructure/{key}/{adapter_name}.py"
                    await self._load_level(f"framework.port.{adapter_name}",adapter_config[i],key,adapter_path)
        
        ms = []
        for name, path in self.managers.items():
            ms.append(await self._load_level(f"framework.manager.{name}", {}, 'Managers', path))
        
        return self.container.get('framework.service.factory').Application(self.container, ms)