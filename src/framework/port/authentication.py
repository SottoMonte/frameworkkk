from abc import ABC, abstractmethod

class port(ABC):

    @flow.action2(inputs=('email','password'),outputs=('access_token',))
    @abstractmethod
    def sign_in(self,email,password):
        pass

    @flow.action2(inputs=('email','password'),outputs=('access_token',))
    @abstractmethod
    def sign_up(self,email,password):
        pass

    @flow.action2(inputs=('access_token',),outputs=('access_token',))
    @abstractmethod
    def sign_out(self,access_token):
        pass

    @flow.action2(inputs=('access_token',),outputs=('access_token',))
    @abstractmethod
    def get_identity(self,access_token):
        pass