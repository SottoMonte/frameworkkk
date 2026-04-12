from abc import ABC, abstractmethod

class port(ABC):

    # Mappa: nome_metodo -> decoratore da applicare automaticamente
    _method_decorators = {
        "sign_in":      flow.result(inputs=("email", "password"), outputs=("session",)),
        "sign_up":      flow.result(inputs=("user",), outputs=("session",)),
        "sign_out":     flow.result(inputs=("session",),          outputs=("session",)),
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

    def seed(self):
        import psycopg2
        try:
            conn = psycopg2.connect(self._db_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                for seed in self._seeds:
                    result     = seed()
                    name       = result[0]
                    check_q    = result[1]
                    exec_q     = result[2]
                    on_exists  = result[3] if len(result) > 3 else None

                    cur.execute(check_q)
                    exists = cur.fetchone()[0]

                    if not exists:
                        cur.execute(exec_q)
                        print(f"[SEED] ✓ {name}: creato")
                    elif on_exists:
                        migration_q = on_exists(cur)
                        if migration_q:
                            cur.execute(migration_q)
                            print(f"[SEED] ↑ {name}: aggiornato")
                        else:
                            print(f"[SEED] ~ {name}: skip")
                    else:
                        print(f"[SEED] ~ {name}: skip")
            conn.close()
        except Exception as e:
            print(f"[SEED] Errore: {e}")