from abc import ABC, abstractmethod

class port(ABC):

    # Mappa: nome_metodo -> decoratore da applicare automaticamente
    _method_decorators = {
        "sign_in":      flow.result(inputs=("email", "password"), outputs=("session",)),
        "sign_up":      flow.result(inputs=("user","password"), outputs=("session",)),
        "sign_out":     flow.result(inputs=("session",),          outputs=("session",)),
        "sign_aid":     flow.result(outputs=("session",), safe_kwargs=True),
        "get_user": flow.result(inputs=("session",),          outputs=("user",)),
    }

    _seeds = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for method_name, decorator in port._method_decorators.items():
            if method_name in cls.__dict__:  # solo se definito direttamente
                original = cls.__dict__[method_name]
                setattr(cls, method_name, decorator(original))

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
    def get_user(self,access_token):
        pass

    @abstractmethod
    def sign_aid(self,email):
        pass

    def migrate(self):
        import psycopg2
        conn = psycopg2.connect(self._db_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            for s in self._migrations:
                try:
                    cur.execute(s["check_sql"])
                    if not cur.fetchone()[0]:
                        cur.execute(s["create_sql"]); print(f"[✓] Driver:{self.name} {s['name']}")
                    elif s["migrate_fn"] and (stmts := s["migrate_fn"](cur)):
                        for stmt in stmts: cur.execute(stmt)
                        print(f"[*] Driver:{self.name} {s['name']}")
                    else: print(f"[~] Driver:{self.name} {s['name']}")
                except Exception as e: print(f"[✗] Driver:{self.name} {s['name']}: {e}"); raise
        conn.close()