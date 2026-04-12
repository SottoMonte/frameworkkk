from typing import Optional
import json
import supabase

def map_supabase_error(error):
    if error == 'Invalid login credentials':
        return [{"field": "email", "message": "Invalid login credentials"},{"field": "password", "message": "Invalid login credentials"}]
    elif error == 'Email change requested':
        return [{"field": "email", "message": "Email change requested"}]
    elif error == 'Email not confirmed':
        return [{"field": "email", "message": "Email not confirmed"}]
    elif error == 'Email already in use':
        return [{"field": "email", "message": "Email already in use"}]
    elif error == 'Password reset requested':
        return [{"field": "password", "message": "Password reset requested"}]
    elif error == 'Password reset failed':
        return [{"field": "password", "message": "Password reset failed"}]
    elif error == 'User not found':
        return [{"field": "email", "message": "User not found"}]
    return [{"field": "General", "message": error}]
    
    

def map_auth_response(provider,auth_res):
    # auth_res è l'oggetto restituito dal client python di supabase
    session = auth_res.session
    user = auth_res.user

    return {
        "id": user.id,
        "providers": {provider: {
            'tokens': {
                'access_token': session.access_token, 
                'refresh_token': session.refresh_token, 
                'expires_at': session.expires_at, 
                'token_type': session.token_type
            },
            'user': {
                "id": user.id,
                "email": user.email,
                **user.user_metadata
            }
        }},
        "user": {
            "id": user.id,
            "email": user.email,
            **user.user_metadata
        }
    }

class Adapter(authentication.port):
    """
    Adapter Supabase stateless per ambienti multi-utente.

    Ogni chiamata crea un client Supabase isolato: nessuna sessione condivisa
    tra richieste concorrenti di utenti diversi.

    Esempio:
        adapter = Adapter(url="https://...", key="anon-key")
        result  = await adapter.authenticate(email="u@example.com", password="secret")
        if result.success:
            tokens = result.data["tokens"]
    """

    def __init__(self, **kwargs):
        url = kwargs.get("url")
        key = kwargs.get("key")
        if not url or not key:
            raise ValueError("Supabase URL e key sono obbligatori.")
        self._url = url
        self._key = key
        self.name = "supabase"

    def _client(self):
        """Client fresco e isolato per ogni richiesta."""
        return supabase.create_client(self._url, self._key)

    @authentication.flow.result(inputs=('email','password'),outputs=('session',))
    async def sign_up(self, **kwargs):
        try:
            response = self._client().auth.sign_up(kwargs)
            return authentication.flow.success(map_auth_response(self.name,response))
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))

    @authentication.flow.result(inputs=('email','password'),outputs=('session',))
    async def sign_in(self, email, password):
        try:
            response  = self._client().auth.sign_in_with_password({"email": email, "password": password})
            return authentication.flow.success(map_auth_response(self.name,response))
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))

    @authentication.flow.result(inputs=('session',),outputs=('session',))
    async def sign_out(self, session):
        try:
            client = self._client()
            client.auth.set_session(session['providers'][self.name]['tokens']['access_token'], "")
            client.auth.sign_out()
            return authentication.flow.success()
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))

    @authentication.flow.result(inputs=('session',),outputs=('user',))
    async def get_identity(self, session):
        try:
            client = self._client()
            client.auth.set_session(session['providers'][self.name]['tokens']['access_token'], "")
            response = client.auth.get_user()
            if not response.user:
                return authentication.flow.error("Utente non autenticato.")
            user = response.user.dict() if hasattr(response.user, "dict") else {}
            return authentication.flow.success(user)
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))