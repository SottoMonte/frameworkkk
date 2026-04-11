from typing import Optional

import supabase

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

    async def sign_up(self, email, password):
        response = self._client().auth.sign_up({"email": email, "password": password})
        token = response.session.access_token if response.session else None
        return {"access_token": token}

    async def sign_in(self, email, password):
        response  = self._client().auth.sign_in_with_password({"email": email, "password": password})
        auth_data = response.dict() if hasattr(response, "dict") else {}
        return {"access_token": auth_data["access_token"]}

    async def sign_out(self, access_token):
        client = self._client()
        client.auth.set_session(access_token, "")
        client.auth.sign_out()
        return True

    async def get_identity(self, access_token):
        client = self._client()
        client.auth.set_session(access_token, "")
        response = client.auth.get_user()
        if not response.user:
            return AuthResult(False, error="Utente non autenticato.")
        user = response.user.dict() if hasattr(response.user, "dict") else {}
        return AuthResult(True, data={"user": user})