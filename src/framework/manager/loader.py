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
from graphlib import TopologicalSorter

from dependency_injector import containers, providers
import tomli
import traceback


# ─────────────────────────────────────────────
# Configurazione globale dei port
# Aggiungere/rimuovere un port: solo questa dict.
# ─────────────────────────────────────────────

PORT_REGISTRY: dict[str, list[str]] = {
    "presentation":   ["defender", "messenger","executor"],
    "persistence":    ["executor"],
    "message":        ["storekeeper", "messenger"],
    "authentication": [],
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

    # Le port-list vengono registrate come "persistences", "presentations" ecc.
    for _port in PORT_REGISTRY:
        locals()[port_list_key(_port)] = providers.Singleton(list, [])
    del _port

    def get(self, name: str):
        attr = getattr(self, name, None)
        if attr is None:
            raise KeyError(f"'{name}' non trovato nel container")
        return attr() if callable(attr) else attr

    def set(self, name: str, obj):
        setattr(self, name, providers.Singleton(lambda o=obj: o))

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
        for k, v in inject.items():
            setattr(mod, k, v)
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def find_class(mod):
        return next(
            (v for v in vars(mod).values()
             if isinstance(v, type) and v.__module__ == mod.__name__),
            None,
        )


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
            cls = self._ml.find_class(mod)
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
        registry   = {s["name"]: s for s in specs}
        dep_graph  = {
            s["name"]: list(set(s.get("mod_deps", [])) | set(s.get("cls_deps", [])))
            for s in specs
        }

        for name in TopologicalSorter(dep_graph).static_order():
            if name in singletons:
                self._c.set(name, singletons[name])
                continue
            if name not in registry:
                continue

            spec = registry[name]
            obj  = await self._b.build(spec)

            if spec.get("is_list"):
                self._c.append_to_port(spec["port"], obj)
            else:
                self._c.set(name, obj)


# ─────────────────────────────────────────────
# ProjectLoader — TOML → lista di spec
# ─────────────────────────────────────────────

class ProjectLoader:
    def __init__(self, container: Container):
        self._c = container

    def load(self, config_path: str) -> list[dict]:
        data = self._read_toml(config_path)
        self._c.config.from_dict(data)
        return [
            self._make_spec(port_name, cfg)
            for port_name, services in data.items()
            if port_name in PORT_REGISTRY
            for cfg in services.values()
        ]

    def _make_spec(self, port: str, cfg: dict) -> dict:
        adapter = cfg.get("adapter")
        print(f"[*] Port: {port}.{adapter}")
        return {
            "name":     "Adapter",
            "path":     f"src/infrastructure/{port}/{adapter}.py",
            "mod_deps": [port],               # es. "persistence"  → modulo framework
            "cls_deps": PORT_REGISTRY[port],  # dipendenze classe adapter
            "port":     port,                 # usato da append_to_port
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
        for name in names:
            obj = self._c.get(name)
            if hasattr(obj, "start"):
                await obj.start()

    async def stop_all(self, names: list[str]):
        for name in names:
            obj = self._c.get(name)
            if hasattr(obj, "stop"):
                await obj.stop()


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# Spec statiche di bootstrap
#
# cls_deps usa "persistences" / "presentations" ecc. — il suffisso
# è coerente con quanto registrato dal Container tramite port_list_key().
# ─────────────────────────────────────────────

_SERVICES: list[dict] = [
    {"name": "container",    "path": "src/framework/service/container.py",  "mod_deps": [],                   "is_class": False, "config": {}},
    {"name": "scheme",       "path": "src/framework/service/scheme.py",     "mod_deps": [],                   "is_class": False, "config": {}},
    {"name": "flow",         "path": "src/framework/service/flow.py",       "mod_deps": ["scheme", "loader"], "is_class": False, "config": {}},
    {"name": "language",     "path": "src/framework/service/language.py",   "mod_deps": ["scheme", "flow"],   "is_class": False, "config": {}},
    {"name": "diagnostic",   "path": "src/framework/service/diagnostic.py", "mod_deps": ["scheme", "flow"],   "is_class": False, "config": {}},
    {"name": "message",      "path": "src/framework/port/message.py",       "mod_deps": [],                   "is_class": False, "config": {}},
    {"name": "presentation", "path": "src/framework/port/presentation.py",  "mod_deps": ["scheme","loader"],  "is_class": False, "config": {}},
    {"name": "persistence",  "path": "src/framework/port/persistence.py",   "mod_deps": [],                   "is_class": False, "config": {}},
]

_MANAGERS: list[dict] = [
    {"name": "loader",      "path": "src/framework/manager/loader.py",      "mod_deps": ["container"],                    "cls_deps": [],                                          "is_class": True, "config": {}},
    {"name": "messenger",   "path": "src/framework/manager/messenger.py",   "mod_deps": ["flow"],                         "cls_deps": ["executor", "messages"],                    "is_class": True, "config": {}},
    {"name": "executor",    "path": "src/framework/manager/executor.py",    "mod_deps": ["flow"],                         "cls_deps": ["defender", "language"],                    "is_class": True, "config": {}},
    {"name": "defender",    "path": "src/framework/manager/defender.py",    "mod_deps": ["flow"],                         "cls_deps": [],                                          "is_class": True, "config": {}},
    {"name": "tester",      "path": "src/framework/manager/tester.py",      "mod_deps": ["language","flow","diagnostic"], "cls_deps": ["loader", "defender", "messenger"],          "is_class": True, "config": {}},
    {"name": "storekeeper", "path": "src/framework/manager/storekeeper.py", "mod_deps": [],                               "cls_deps": ["executor", "persistences"],                "is_class": True, "config": {}},
    {"name": "presenter",   "path": "src/framework/manager/presenter.py",   "mod_deps": [],                               "cls_deps": ["executor", "presentations"],               "is_class": True, "config": {}},
]

_MANAGERS_WITH_ARGS: set[str] = {"executor", "defender", "tester"}


def _inject_args(specs: list[dict], args) -> list[dict]:
    return [
        {**s, "config": {**s["config"], "args": args}}
        if s["name"] in _MANAGERS_WITH_ARGS else s
        for s in specs
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

    def get(self, name: str):
        return self._container.get(name)

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
        managers      = _inject_args(_MANAGERS, args)
        project_specs = self._project.load("pyproject.toml") if '--test' not in args else []

        await self._batch.run(
            _SERVICES + managers + project_specs,
            singletons={"loader": self, "container": self._container},
        )

        stop_event = asyncio.Event()
        loop       = asyncio.get_running_loop()

        def _on_signal():
            print("\n[!] Shutdown richiesto.")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)

        print("[*] Framework bootstrapped. Running...")

        manager_names = [s["name"] for s in managers]
        try:
            await self._lifecycle.start_all(manager_names)
            await stop_event.wait()
        except Exception as e:
            print(f"[!] Errore: {e}")
            traceback.print_exc()
        finally:
            await self._lifecycle.stop_all(manager_names)
            print("[*] Framework spento correttamente.")