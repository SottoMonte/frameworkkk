from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class Port(Protocol):

    def loader(self, config: dict[str, Any]) -> None:
        """Inizializza o configura l'adapter con i dati passati dal framework."""
        ...

    async def get(self, endpoint: str, context: dict[str, Any]) -> Any:
        """Gestisce una richiesta in ingresso di tipo GET."""
        ...

    async def post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        """Gestisce una richiesta in ingresso di tipo POST."""
        ...

    async def can(self, identity: str, action: str) -> bool:
        """Verifica i permessi di sicurezza (ACL/RBAC) per un determinato modulo."""
        ...