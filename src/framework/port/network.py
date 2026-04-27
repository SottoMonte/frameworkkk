from abc import ABC, abstractmethod

class port(ABC):
    _method_decorators = {
        "provision": flow.result(inputs=("intent",), outputs=("deployment",)),
        "monitor": flow.result(outputs=("status",)),
        "status": flow.result(outputs=("status",)),
        "route": flow.result(inputs=("application", "requirements"), outputs=("route",)),
    }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for method_name, decorator in port._method_decorators.items():
            if method_name in cls.__dict__:
                original = cls.__dict__[method_name]
                setattr(cls, method_name, decorator(original))

    @abstractmethod
    async def provision(self, intent: dict):
        pass

    @abstractmethod
    async def monitor(self):
        pass

    @abstractmethod
    async def route(self, application: dict, requirements: dict):
        pass

    @abstractmethod
    async def status(self):
        pass

    @abstractmethod
    def deploy(self, deploy_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Deploya l'applicazione sulla rete/hosting adatto (es. container su cloud, static su CDN)."""
        pass

    @abstractmethod
    def scale(self, scale_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Scala risorse di hosting (es. aumenta VM, replica container)."""
        pass

    @abstractmethod
    def migrate(self, migrate_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Migra l'applicazione tra reti/provider (es. da on-prem a cloud)."""
        pass
