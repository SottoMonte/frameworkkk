from typing import Optional
import json
import supabase

# ── helpers ───────────────────────────────────────────────────────────────────

TYPE_MAP = {
    "string": "text", "integer": "integer", "float": "numeric",
    "boolean": "boolean", "date": "date", "datetime": "timestamp",
}
AUTH_FIELDS = {"id", "email", "password"}

def _pg_type(meta):
    return TYPE_MAP.get(meta.get("type", "string"), "text")

def _migration_ddl(desired, existing):
    stmts  = [f"alter table public.profiles add column {c} {t};"
              for c, t in desired.items() if c not in existing]
    stmts += [f"alter table public.profiles alter column {c} type {t} using {c}::{t};"
              for c, t in desired.items() if c in existing and existing[c] != t]
    stmts += [f"alter table public.profiles drop column {c};"
              for c in existing if c not in desired]
    return stmts

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
        db_url = kwargs.get("db_url")
        self._schema = kwargs.get("models").get("user")
        if not url or not key:
            raise ValueError("Supabase URL e key sono obbligatori.")
        self._url = url
        self._key = key
        self._db_url = db_url
        self.name = "supabase"
        self._seeds = [
            self._seed_profiles_table,
            self._seed_profiles_function,
            self._seed_profiles_trigger,
        ]

        if db_url:
            self.seed()

    # ── schema helpers ────────────────────────────────────────────────────────

    def _user_fields(self) -> dict:
        return {k: v for k, v in self._schema.items() if k not in AUTH_FIELDS}

    def _desired_cols(self) -> dict[str, str]:
        return {f: _pg_type(m) for f, m in self._user_fields().items()}

    # ── seed factories ────────────────────────────────────────────────────────

    def _seed_profiles_table(self):
        cols = (
            ["id uuid references auth.users(id) on delete cascade primary key"]
            + [f"{f} {t}" for f, t in self._desired_cols().items()]
            + ["created_at timestamp default now()"]
        )

        def on_exists(cur):
            cur.execute("""
                select column_name, data_type
                from information_schema.columns
                where table_schema='public' and table_name='profiles'
                  and column_name not in ('id','created_at')
            """)
            stmts = _migration_ddl(self._desired_cols(), dict(cur.fetchall()))
            return "\n".join(stmts) if stmts else None

        return (
            "profiles table",
            "select exists(select 1 from information_schema.tables where table_schema='public' and table_name='profiles')",
            f"create table public.profiles (\n  {', '.join(cols)}\n);",
            on_exists,
        )

    def _seed_profiles_function(self):
        fields     = list(self._user_fields())
        ins_fields = ", ".join(["id"] + fields)
        ins_values = ", ".join(
            ["new.id"] + [f"new.raw_user_meta_data->>'{f}'" for f in fields]
        )

        def fn():
            return f"""
                create or replace function handle_new_user() returns trigger as $$
                begin
                    insert into public.profiles ({ins_fields}) values ({ins_values});
                    return new;
                end;
                $$ language plpgsql security definer;
            """

        def on_exists(cur):
            import re
            cur.execute("select prosrc from pg_proc where proname='handle_new_user'")
            row = cur.fetchone()
            if not row:
                return fn()
            match = re.search(r"insert into public\.profiles \((.+?)\)", row[0])
            current_fields = match.group(1).replace(" ", "") if match else ""
            return fn() if current_fields != ins_fields.replace(" ", "") else None

        return (
            "function handle_new_user",
            "select exists(select 1 from pg_proc where proname='handle_new_user')",
            fn(),
            on_exists,
        )

    def _seed_profiles_trigger(self):
        return (
            "trigger on_auth_user_created",
            "select exists(select 1 from pg_trigger where tgname='on_auth_user_created')",
            """
                create trigger on_auth_user_created
                after insert on auth.users
                for each row execute procedure handle_new_user();
            """,
        )
    # ── Supabase client ───────────────────────────────────────────────────────

    def _client(self):
        return supabase.create_client(self._url, self._key)

    def _authed_client(self, session):
        tokens = session["providers"][self.name]["tokens"]
        client = self._client()
        client.auth.set_session(
            tokens["access_token"],
            tokens.get("refresh_token", ""),
        )
        return client

    # ── port implementation ───────────────────────────────────────────────────

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