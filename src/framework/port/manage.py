from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class Port(Protocol):

    async def start(self, endpoint: str, context: dict[str, Any]) -> Any:
        """Inizializza il port."""
        ...

    async def stop(self, endpoint: str, context: dict[str, Any]) -> Any:
        """Arresta il port."""
        ...