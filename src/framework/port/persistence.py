from abc import ABC, abstractmethod

class port(ABC):

    _method_decorators = {
        "create":      flow.result(inputs=("session","storekeeper"), outputs=("session",)),
        "read":      flow.result(inputs=("session","storekeeper"), outputs=("session",)),
        "update":     flow.result(inputs=("session","storekeeper"), outputs=("session",)),
        "delete":     flow.result(inputs=("session","storekeeper"), outputs=("session",)),
        "query": flow.result(inputs=("session","storekeeper"), outputs=("session",)),
        "view": flow.result(inputs=("session","storekeeper"), outputs=("session",)),
    }

    _seeds = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for method_name, decorator in port._method_decorators.items():
            if method_name in cls.__dict__:  # solo se definito direttamente
                original = cls.__dict__[method_name]
                setattr(cls, method_name, decorator(original))

    @abstractmethod
    async def create(self,*services,**constants):
        pass

    @abstractmethod
    def read(self,*services,**constants):
        pass

    @abstractmethod
    async def update(self,*services,**constants):
        pass

    @abstractmethod
    async def delete(self,*services,**constants):
        pass

    @abstractmethod
    async def query(self,*services,**constants):
        pass

    @abstractmethod
    async def view(self,*services,**constants):
        pass