import os, sys, inspect, json, uuid, ast, types, importlib.util
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Type, Optional, Iterator
from graphlib import TopologicalSorter
from jinja2 import Environment, BaseLoader
import tomli
from pathlib import Path


# ── Errori ────────────────────────────────────────────────────────────────────

class DiscoveryError(Exception):
    """Uno o più componenti dichiarati in configurazione non sono stati trovati."""


# ── ComponentDescriptor ──────────────────────────────────────────────────────

class ComponentKind(Enum):
    MANAGER = 'manager'
    ADAPTER = 'adapter'


@dataclass
class ComponentDescriptor:
    """Metadati di un componente scoperto: nessuna istanza, solo reflection."""
    cls: Type
    kind: ComponentKind
    dependencies: dict[str, Type]      # nome_parametro -> annotazione
    config: dict
    interface: Optional[Type] = None


# ── Registry ──────────────────────────────────────────────────────────────────

class Registry:
    """
    Il database dei componenti del framework.

    Responsabilità:
    - scopre plugin (discover)
    - carica moduli (load_module / load_core)
    - legge reflection (dependencies, imports)
    - mantiene i descriptor (components)
    - calcola l'ordine topologico (topological_order, build_order)
    - espone manager / adapter / service come un'unica collezione
    - segnala errori di discovery invece di ignorarli in silenzio (check)
    """

    def __init__(self):
        self.components: list[ComponentDescriptor] = []
        self.errors: list[str] = []
        self._loaded_core: list[str] = []  # nomi dei moduli 'service'/'port' del framework core

    # ── caricamento moduli ───────────────────────────────────────────────────

    def _pkg(self, name: str) -> types.ModuleType:
        """
        Crea i package intermedi framework.x.y se non esistono ancora.

        Necessario perché il namespace dotted (es. 'framework.adapter.persistence.sqlite')
        non corrisponde alla struttura reale su disco (es. 'src/infrastructure/persistence/
        sqlite.py'): non è un vero package Python, quindi importlib da solo non basta a
        risolvere i genitori — li costruiamo come moduli sintetici vuoti.
        """
        if not name or name in sys.modules:
            return sys.modules.get(name)
        pkg = types.ModuleType(name)
        pkg.__path__ = []
        pkg.__package__ = name.rpartition('.')[0]
        sys.modules[name] = pkg
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            setattr(self._pkg(parent), child, pkg)
        return pkg

    async def load_module(self, name: str, path: str, extra: dict = None) -> types.ModuleType:
        """Carica ed esegue un file come modulo, usando importlib per spec/loader/exec."""
        if name in sys.modules:
            return sys.modules[name]

        self._pkg(name.rpartition('.')[0])

        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"'{name}': impossibile creare lo spec per '{path}'")

        mod = importlib.util.module_from_spec(spec)
        if extra:
            mod.__dict__.update(extra)

        sys.modules[name] = mod
        if '.' in name:
            pkg, short = name.rsplit('.', 1)
            setattr(self._pkg(pkg), short, mod)

        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            del sys.modules[name]
            raise RuntimeError(f"'{name}': {e}") from e

        print(f"[+] {name}")
        return mod

    async def load_core(self, services: dict[str, str], ports: dict[str, str],
                         extra_by_name: dict[str, dict] = None) -> None:
        """
        Carica i moduli 'service' e 'port' del framework core in ordine topologico,
        calcolato sui loro import reciproci. Non sono componenti DI: sono moduli
        eseguiti una volta sola (non hanno un costruttore da iniettare).
        """
        extra_by_name = extra_by_name or {}
        all_mods = services | ports
        codes, deps = {}, {}
        for short, path in all_mods.items():
            ns = f"framework.{'service' if short in services else 'port'}.{short}"
            if ns in sys.modules:
                continue
            code = open(path, 'rb').read().decode()
            codes[short] = (code, path, ns)
            imports = {n.split('.')[-1] for n in self.imports(code)}
            deps[short] = imports & all_mods.keys()
        for name in self.topological_order(deps):
            if name not in codes:
                continue
            _, path, ns = codes[name]
            await self.load_module(ns, path, extra_by_name.get(name))
            self._loaded_core.append(ns)

    def core_attribute(self, module_short_name: str, attr: str) -> Any:
        """
        Recupera un attributo da un modulo core già caricato (es. la classe
        'Application' dal modulo 'factory'), senza che il chiamante debba
        conoscere il nome dotted completo del modulo.
        """
        ns = next((m for m in self._loaded_core if m.endswith(f'.{module_short_name}')), None)
        if ns is None:
            raise RuntimeError(f"Modulo core '{module_short_name}' non caricato.")
        mod = sys.modules[ns]
        if not hasattr(mod, attr):
            raise RuntimeError(f"'{attr}' non trovato nel modulo core '{module_short_name}'.")
        return getattr(mod, attr)

    # ── reflection ───────────────────────────────────────────────────────────

    @staticmethod
    def imports(code: str) -> list[str]:
        try:
            tree = ast.parse(code)
        except Exception:
            return []
        seen = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names: seen[a.name] = None
            elif isinstance(n, ast.ImportFrom) and n.module:
                seen[n.module] = None
        return list(seen)

    @staticmethod
    def dependencies(cls: Type) -> dict[str, Type]:
        """Legge le annotazioni del costruttore: nome parametro -> tipo (escluso self)."""
        return {
            name: p.annotation
            for name, p in inspect.signature(cls.__init__).parameters.items()
            if name != 'self' and p.annotation is not inspect.Parameter.empty
        }

    @staticmethod
    def is_port_list(ann: Any) -> bool:
        return (hasattr(ann, '__origin__') and ann.__origin__ is list
                and bool(getattr(ann, '__args__', None)))

    def file_dependencies(self, file_path: str, root: str = "src") -> list[str]:
        """Restituisce la lista dei file Python corrispondenti ai moduli importati."""
        try:
            tree = ast.parse(Path(file_path).read_text(encoding="utf-8"))
        except Exception:
            return []

        deps = {file_path}

        def add(path: Path):
            if path.exists() and path.is_file():
                deps.add(str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add(Path(root, *alias.name.split(".")).with_suffix(".py"))
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                base = Path(root, *node.module.split("."))
                module_file = base.with_suffix(".py")
                if module_file.exists():
                    add(module_file)
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = (base / alias.name).with_suffix(".py")
                    if candidate.exists():
                        add(candidate)

        return sorted(deps)

    # ── discover / register ──────────────────────────────────────────────────

    async def discover(self, name: str, path: str, kind: ComponentKind,
                        config: dict, interface: Type = None) -> Optional[ComponentDescriptor]:
        """Carica un modulo e ne registra il descriptor. Zero istanze. Errori accumulati, non persi."""
        if not os.path.isfile(path):
            msg = f"modulo non trovato: '{path}' (atteso per '{name}')"
            self.errors.append(msg)
            print(f"[!] {msg}")
            return None

        class_name = 'Manager' if kind is ComponentKind.MANAGER else 'Adapter'
        mod = await self.load_module(name, path)
        cls = getattr(mod, class_name, None)
        if cls is None:
            msg = f"classe '{class_name}' non trovata in '{name}' ({path})"
            self.errors.append(msg)
            print(f"[!] {msg}")
            return None

        descriptor = ComponentDescriptor(
            cls=cls, kind=kind, interface=interface,
            dependencies=self.dependencies(cls), config=config)
        self.register(descriptor)

        cfg_name = config.get('name') if isinstance(config, dict) else None
        details = f" name='{cfg_name}'" if cfg_name else ''
        print(f"[~] {class_name} '{cls.__name__}' scoperto{details}")
        return descriptor

    def register(self, descriptor: ComponentDescriptor) -> None:
        self.components.append(descriptor)

    def check(self) -> None:
        """Solleva un errore riassuntivo se la discovery ha incontrato problemi: fail fast
        invece di proseguire con manager/adapter mancanti che falliscono più avanti in modo criptico."""
        if self.errors:
            details = "\n".join(f"  - {e}" for e in self.errors)
            raise DiscoveryError(f"Discovery fallita per {len(self.errors)} componente/i:\n{details}")

    # ── query sulla collezione ───────────────────────────────────────────────

    def descriptors(self) -> list[ComponentDescriptor]:
        return list(self.components)

    def managers(self) -> Iterator[ComponentDescriptor]:
        return (c for c in self.components if c.kind is ComponentKind.MANAGER)

    def adapters(self) -> Iterator[ComponentDescriptor]:
        return (c for c in self.components if c.kind is ComponentKind.ADAPTER)

    def by_kind(self, kind: ComponentKind) -> Iterator[ComponentDescriptor]:
        return (c for c in self.components if c.kind is kind)

    def services(self) -> list[str]:
        """Nomi dei moduli 'service'/'port' del framework core già caricati."""
        return list(self._loaded_core)

    def resolve(self, cls: Type) -> Optional[ComponentDescriptor | list[ComponentDescriptor]]:
        """Restituisce il/i descriptor registrati per una classe."""
        found = [c for c in self.components if c.cls is cls]
        if not found:
            return None
        return found[0] if len(found) == 1 else found

    # ── ordinamento ───────────────────────────────────────────────────────────

    @staticmethod
    def topological_order(graph: dict) -> list:
        return list(TopologicalSorter(graph).static_order())

    def build_order(self, kind: ComponentKind) -> list[Type]:
        """
        Ordine topologico delle classi di un certo kind, basato sulle sole
        dipendenze verso classi dello stesso kind (le list[Port] sono risolte
        a parte, via container). Generalizza il vecchio 'manager_build_order':
        vale anche per gli adapter, nel caso uno dipenda direttamente da un altro.
        Più classi (config multiple dello stesso adapter) collassano su un solo nodo.
        """
        descriptors = list(self.by_kind(kind))
        cls_set = {d.cls for d in descriptors}
        graph: dict[Type, set[Type]] = {cls: set() for cls in cls_set}
        for d in descriptors:
            graph[d.cls] |= {
                dep for dep in d.dependencies.values()
                if not self.is_port_list(dep) and dep in cls_set
            }
        return [c for c in self.topological_order(graph) if c in cls_set]


# ── Container ─────────────────────────────────────────────────────────────────

class Container:
    """
    Vero Dependency Injection Container.

    Responsabilità:
    - costruisce istanze (build)
    - risolve dipendenze (_resolve_kwargs)
    - gestisce singleton (manager) e istanze multiple (adapter con più config)
    - inietta le porte nei manager (inject_ports)
    """

    def __init__(self):
        self._instances: dict[Type, list[Any]] = {}
        self._ports: dict[Type, list] = {}
        self._pending_ports: dict[Type, dict[str, tuple[Type, list]]] = {}

    def put(self, cls: Type, obj: Any, singleton: bool = True) -> None:
        """
        singleton=True (default, usato per i manager e per registrazioni manuali
        come Loader stesso): sostituisce l'eventuale istanza precedente — un solo
        oggetto per classe. singleton=False (usato per gli adapter): accumula,
        così più istanze configurate della stessa classe adapter convivono invece
        di sovrascriversi silenziosamente.
        """
        if singleton:
            self._instances[cls] = [obj]
        else:
            self._instances.setdefault(cls, []).append(obj)

    def get(self, cls: Type) -> Any:
        """Ultima istanza registrata per cls (l'unica, se singleton)."""
        instances = self._instances.get(cls)
        return instances[-1] if instances else None

    def get_all(self, cls: Type) -> list:
        """Tutte le istanze registrate per cls (utile per gli adapter multi-istanza)."""
        return list(self._instances.get(cls, []))

    def add_port(self, iface: Type, obj: Any) -> None:
        self._ports.setdefault(iface, []).append(obj)

    def get_port(self, iface: Type) -> list:
        return list(self._ports.get(iface, []))

    def build(self, descriptor: ComponentDescriptor) -> Any:
        """Istanzia il componente descritto, risolvendo le dipendenze dal container."""
        kwargs = self._resolve_kwargs(descriptor)
        instance = descriptor.cls(**kwargs, **descriptor.config)
        self.put(descriptor.cls, instance, singleton=descriptor.kind is ComponentKind.MANAGER)
        if descriptor.kind is ComponentKind.ADAPTER and descriptor.interface:
            self.add_port(descriptor.interface, instance)
        return instance

    def _resolve_kwargs(self, descriptor: ComponentDescriptor) -> dict:
        """
        Per i manager le list[Port] diventano liste vuote la cui referenza
        viene salvata per inject_ports(). Per gli adapter le list[Port]
        vengono risolte subito dal container.
        """
        cls = descriptor.cls
        kwargs = {}
        for pname, ann in descriptor.dependencies.items():
            if Registry.is_port_list(ann):
                iface = ann.__args__[0]
                if descriptor.kind is ComponentKind.MANAGER:
                    port_list: list = []
                    self._pending_ports.setdefault(cls, {})[pname] = (iface, port_list)
                    kwargs[pname] = port_list
                else:
                    kwargs[pname] = self.get_port(iface)
            else:
                dep = self.get(ann)
                if dep is None:
                    raise RuntimeError(f"'{cls.__name__}': dipendenza '{ann}' non trovata.")
                kwargs[pname] = dep
        return kwargs

    def inject_ports(self) -> None:
        """Popola le liste vuote dei manager con gli adapter ora costruiti."""
        for cls, pending in self._pending_ports.items():
            for pname, (iface, port_list) in pending.items():
                adapters = self.get_port(iface)
                port_list.extend(adapters)
                print(f"[~] '{cls.__name__}.{pname}' ← {[a.__class__.__name__ for a in adapters]}")


# ── Infrastructure ───────────────────────────────────────────────────────────

class Infrastructure:
    """TOML, JSON, Jinja, schemi, risorse: l'I/O di configurazione del framework."""

    def __init__(self):
        self.jinja_env = Environment(loader=BaseLoader())
        self.jinja_env.filters.setdefault('tojson', json.dumps)
        self.jinja_env.globals['uuid4'] = lambda: str(uuid.uuid4())
        self.schemes: dict[str, Any] = {}

    def load_toml(self, path: str) -> dict:
        return tomli.loads(open(path, 'rb').read().decode())

    async def load_schemes(self, directories: list[str]) -> dict:
        raw: dict[str, Any] = {}
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

        cache: dict[str, Any] = {}

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
        try:
            from cerberus import schema_registry
            for name, schema in final.items():
                try: schema_registry.add(name, schema)
                except Exception: pass
        except ImportError:
            pass

        self.schemes = final
        return final

    async def resource(self, path) -> str:
        if str(path).startswith('application/'):
            path = 'src/' + path
        return open(path, 'rb').read().decode()


# ── Loader ────────────────────────────────────────────────────────────────────

_BOOTSTRAPPED = False   # guardia di processo: vedi Loader.bootstrap()


class Loader:
    """Coordina Container, Registry e Infrastructure. Nessuna logica propria."""

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
        'defender':     'src/framework/manager/defender.py',
        'messenger':    'src/framework/manager/messenger.py',
        'presenter':    'src/framework/manager/presenter.py',
        'storekeeper':  'src/framework/manager/storekeeper.py',
        'orchestrator': 'src/framework/manager/orchestrator.py',
        'networker':    'src/framework/manager/networker.py',
    }
    # (short_name_modulo_core, nome_attributo): dove trovare la classe Application
    application_factory: tuple[str, str] = ('factory', 'Application')

    def __init__(self):
        self.container = Container()
        self.registry = Registry()
        self.infrastructure = Infrastructure()
        self.session: Any = None
        self.container.put(Loader, self)
        sys.modules['framework.loader'] = sys.modules[__name__]

    # ── discovery coordinata ──────────────────────────────────────────────────

    async def _discover_managers(self, managers_config: dict) -> None:
        for short, path in self.managers.items():
            await self.registry.discover(
                f'framework.manager.{short}', path,
                ComponentKind.MANAGER, managers_config.get(short, {}))

    async def _discover_adapters(self, config: dict) -> None:
        for port_key in self.ports:
            port_mod = sys.modules.get(f"framework.port.{port_key}")
            interface = getattr(port_mod, 'Port', None) if port_mod else None
            for adapter_name, raw_cfg in config.get(port_key, {}).items():
                cfgs = raw_cfg if isinstance(raw_cfg, list) else [raw_cfg]
                path = f'src/infrastructure/{port_key}/{adapter_name}.py'
                for cfg in cfgs:
                    await self.registry.discover(
                        f'framework.adapter.{port_key}.{adapter_name}', path,
                        ComponentKind.ADAPTER, cfg, interface)

    # ── build coordinato ──────────────────────────────────────────────────────

    def _build_managers(self) -> list[Any]:
        by_cls = {d.cls: d for d in self.registry.managers()}
        instances = []
        for cls in self.registry.build_order(ComponentKind.MANAGER):
            instance = self.container.build(by_cls[cls])
            print(f"[✓] Manager '{cls.__name__}'")
            instances.append(instance)
        return instances

    def _build_adapters(self) -> None:
        by_cls: dict[Type, list[ComponentDescriptor]] = {}
        for d in self.registry.adapters():
            by_cls.setdefault(d.cls, []).append(d)

        for cls in self.registry.build_order(ComponentKind.ADAPTER):
            for descriptor in by_cls[cls]:
                instance = self.container.build(descriptor)
                cfg_name = descriptor.config.get('name') if isinstance(descriptor.config, dict) else None
                extra = f" name='{cfg_name}'" if cfg_name else ''
                iface = descriptor.interface
                print(f"[✓] Adapter '{cls.__name__}'{extra}" +
                      (f" → {iface.__name__}" if iface else ""))

    # ── accessor di comodo ────────────────────────────────────────────────────

    def get_managers(self) -> dict[str, Any]:
        """Restituisce un dizionario con 'nome_manager' -> Istanza."""
        result = {"loader": self}
        for descriptor in self.registry.managers():
            instance = self.container.get(descriptor.cls)
            if instance is not None:
                module_name = descriptor.cls.__module__.split('.')[-1]
                result[module_name] = instance
        return result

    async def resource(self, path):
        return await self.infrastructure.resource(path)

    def file_dependencies(self, file_path: str, root: str = "src") -> list[str]:
        return self.registry.file_dependencies(file_path, root)

    async def _start_entry(self, entry_cls: Type) -> Any:
        """
        Avvia 'a freddo' il manager d'ingresso (il 'defender') e crea la sessione.
        Passo preliminare al bootstrap: la sessione deve esistere già prima che
        'Application' possa essere costruita. Il defender verrà avviato di nuovo
        'a caldo' dentro Application.start(), stavolta insieme a tutti gli altri
        manager e con la sessione già disponibile — vedi framework.service.factory.
        """
        entry = self.container.get(entry_cls)
        if entry is None:
            raise RuntimeError(f"Manager d'ingresso '{entry_cls.__name__}' non costruito.")
        await entry.start()
        self.session = await entry.session_create()
        print(f"[*] Sessione creata: {self.session}")
        return self.session

    # ── bootstrap ─────────────────────────────────────────────────────────────

    async def bootstrap(self, config_toml_path: str) -> Any:
        """
        1. discover  — carica file, legge firme, zero istanze
        2. check     — fail fast se manca qualcosa in configurazione
        3. managers  — costruisce in ordine topologico (list[Port] = [])
        4. adapters  — costruisce; trovano i manager pronti
        5. inject    — popola le liste vuote dei manager via mutazione
        """
        global _BOOTSTRAPPED
        if _BOOTSTRAPPED:
            raise RuntimeError(
                "Bootstrap già eseguito in questo processo: i moduli 'framework.*' "
                "restano in cache in sys.modules e non possono essere ricaricati per "
                "un secondo Loader. Usare un nuovo processo/interprete."
            )
        _BOOTSTRAPPED = True

        await self.infrastructure.load_schemes(
            ['src/framework/scheme', 'src/application/model'])
        await self.registry.load_core(
            self.services, self.ports,
            extra_by_name={'scheme': {
                'schemes': self.infrastructure.schemes,
                'jinja_env': self.infrastructure.jinja_env,
            }})

        config = self.infrastructure.load_toml(config_toml_path)
        managers_config = config.get('manager', {})

        print('\n[*] Discover...')
        await self._discover_managers(managers_config)
        await self._discover_adapters(config)
        self.registry.check()

        print('\n[*] Build...')
        instances = self._build_managers()
        self._build_adapters()
        self.container.inject_ports()

        entry_cls = next(d.cls for d in self.registry.managers())  # il primo dichiarato ('defender')
        await self._start_entry(entry_cls)

        Application = self.registry.core_attribute(*self.application_factory)
        return Application(self.container, instances, self.session)