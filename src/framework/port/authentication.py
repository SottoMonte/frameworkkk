from abc import ABC, abstractmethod

class port(ABC):

    @abstractmethod
    def sign_in(self,email,password):
        pass

    @abstractmethod
    def sign_up(self,email,password):
        pass

    @abstractmethod
    def sign_out(self,access_token):
        pass

    @abstractmethod
    def get_identity(self,access_token):
        pass