import framework.service.load as load
from framework.service.context import container
import framework.service.flow as flow

class loader:
    """
    Manager that handles resource loading and bootstrapping by delegating to the load service.
    """
    def __init__(self, **constants):
        self.config = constants
        self.resources = {}
        self.services = {}
        self.dependencies = {
            "context": [],
            "flow": ["context"],
            "scheme": ["flow"],
            "language": ["flow", "scheme"],
            "load": ["flow", "scheme", "language", "context"],
            "test": ["flow"],
            "factory": ["flow"],
            "diagnostic": ["flow"]
        }

    def _get_load_order(self):
        """Calculates the loading order using a topological sort (DFS)."""
        order = []
        visited = set()
        stack = set()

        def visit(node):
            if node in stack:
                raise RuntimeError(f"Ciclo di dipendenze rilevato: {node}")
            if node not in visited:
                stack.add(node)
                for dep in self.dependencies.get(node, []):
                    visit(dep)
                stack.remove(node)
                visited.add(node)
                order.append(node)

        for node in self.dependencies:
            visit(node)
        return order

    async def _initialize_services(self):
        """Loads and injects dependencies into core services in the correct order."""
        order = self._get_load_order()
        for name in order:
            path = f"framework/service/{name}.py"
            # Carichiamo il servizio via load.resource per abilitare proxy e transazioni
            res = await load.resource(path=path)
            
            # Se res è un errore (dict con success=False), saltiamo o logghiamo
            if isinstance(res, dict) and res.get('success') is False:
                print(f"[ERROR] Fallimento caricamento {name}: {res.get('errors')}")
                continue

            service_module = res
            # Iniezione delle dipendenze dichiarate
            for dep_name in self.dependencies.get(name, []):
                if dep_name in self.services:
                    setattr(service_module, dep_name, self.services[dep_name])
            
            self.services[name] = service_module
            self.resources[path] = service_module
        return self.services

    async def resource(self, **kwargs):
        """
        Loads a resource using the load service.
        """
        path = kwargs.get('path')
        if not path:
            return {"success": False, "errors": ["Missing path"]}

        if path in self.resources:
            return {"success": True, "data": self.resources[path]}
        else:
            res = await load.resource(**kwargs)
            # Se res è un errore esplicito, ritornalo
            if isinstance(res, dict) and res.get('success') is False:
                return res
            
            # Altrimenti res è il dato caricato
            self.resources[path] = res
            return {"success": True, "data": res}

    async def bootstrap(self):
        """
        Bootstraps the framework by initializing core services first.
        """
        # 1. Inizializziamo i servizi core in ordine di dipendenza
        await self._initialize_services()
        
        # 2. Procediamo con il bootstrap dello strato applicativo (bootstrap.dsl)
        # Usiamo preferibilmente la versione 'iniettata' del servizio load se disponibile
        load_service = self.services.get('load', load)
        return await load_service.bootstrap()
    
    async def register(self, **kwargs):
        """
        Registers a dependency injection entry.
        """
        load_service = self.services.get('load', load)
        return await load_service.register(**kwargs)