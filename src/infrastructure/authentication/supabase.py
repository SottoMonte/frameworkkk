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

    async def sign_up(self, user):
        try:
            # Creiamo una copia per non sporcare l'oggetto originale
            user_data = user.copy()
            email = user_data.pop("email")
            password = user_data.pop("password")
            
            # Passiamo i parametri correttamente
            response = self._client().auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_data # Tutto ciò che resta sono parametri aggiuntivi
                }
            })
            return authentication.flow.success(map_auth_response(self.name, response))
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))

    async def sign_in(self, email, password):
        try:
            response  = self._client().auth.sign_in_with_password({"email": email, "password": password})
            return authentication.flow.success(map_auth_response(self.name,response))
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))

    async def sign_out(self, session):
        try:
            tokens = session['providers'][self.name]['tokens']
            client = self._client()
            # IMPORTANTE: Passa sia access che refresh token se disponibili
            client.auth.set_session(tokens['access_token'], tokens.get('refresh_token', ""))
            
            # Opzionale: puoi forzare lo scope globale
            client.auth.sign_out({"scope": "global"})
            return authentication.flow.success()
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))

    async def get_user(self, session):
        try:
            tokens = session['providers'][self.name]['tokens']
            client = self._client()
            client.auth.set_session(tokens['access_token'], tokens.get('refresh_token', ""))
            
            response = client.auth.get_user()
            
            if not response.user:
                return authentication.flow.error("Utente non autenticato.")
            
            # Restituiamo un formato coerente con il resto dell'app
            user = response.user
            return authentication.flow.success({
                "id": user.id,
                "email": user.email,
                **user.user_metadata
            })
        except Exception as e:
            return authentication.flow.error(map_supabase_error(str(e)))