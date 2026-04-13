from secrets import token_urlsafe
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs, urljoin

class defender:
    def __init__(self, **constants):
        """
        Inizializza la classe Defender con i provider specificati.

        :param constants: Configurazioni iniziali, deve includere 'providers'.
        """
        self.language = constants.get('language')
        self.loader = constants.get('loader')
        self.config = constants.get('project', dict())
        self.authentications = constants.get('authentications', [])
        self.interpreter = self.language.Interpreter()
        self.policies = {}

    async def stop(self):
        await self.interpreter.stop()
    
    async def start(self):
        await self.interpreter.start()
        policies = self.config.get('policy', dict())
        await self.create_session('demo', {})
        for policy in policies:
            filename = policies.get(policy)
            path = f"src/application/policy/{policy}/{filename}"
            code = await self.loader.resource(path)
            await self.add_file(path, code)
            self.policies[policy] = await self.run_session('demo', path)
            print(f"[+] Policy: {policy}/{filename}")

    async def add_file(self, name, source):
        return await self.interpreter.add_file(name, source)

    async def create_session(self, session, env={}):
        return await self.interpreter.create_session(session, env|self.language.DSL_FUNCTIONS)

    async def run_session(self, session, file, env={}):
        return await self.interpreter.run_session(session, file, env|self.language.DSL_FUNCTIONS)

    def get_policy(self, policy):
        return self.policies.get(policy)

    @flow.result(inputs=('session',))
    async def new_session(self, session):
        return flow.success(session)
    
    @flow.result(outputs=('session',))
    async def terminate(self, session, **constants) -> bool:
        """
        Termina la sessione di un utente specificato.

        :param constants: Deve includere 'identifier'.
        :return: True se la sessione è stata terminata, False se l'utente non esiste.
        """

        for authentication in self.authentications:
            session_result = await authentication.sign_out(session)
            if session_result.get('success'):
                session.update(session_result['outputs'])
            else:
                return flow.error(session_result['errors'])

        return flow.success(session)

    @flow.result(outputs=('session',))
    async def reinstate(self, session, **constants):
        """
        Autentica un utente utilizzando i provider configurati.

        :param constants: Deve includere 'identifier', 'ip' e credenziali.
        :return: Dizionario di sessione aggiornato se l'autenticazione ha successo, altrimenti None.
        """

        for authentication in self.authentications:
            #provider_persistence = authentication.config.get('persistence')
            session_result = await authentication.sign_aid(**constants)
            if session_result.get('success'):
                session.setdefault('providers', {})
                session.setdefault('user', {})
                session['providers'][authentication.name] = session_result['outputs']['providers'][authentication.name]
                session['user'] |= session_result['outputs']['user']
            else:
                return flow.error(session_result['errors'])
            '''if provider_persistence:
                await storekeeper.store(repository='sessions',payload=session)
                pass'''
        return flow.success(session)

    @flow.result(outputs=('session',))
    async def authenticate(self, session, **constants):
        """
        Autentica un utente utilizzando i provider configurati.

        :param constants: Deve includere 'identifier', 'ip' e credenziali.
        :return: Dizionario di sessione aggiornato se l'autenticazione ha successo, altrimenti None.
        """
        for authentication in self.authentications:
            #provider_persistence = authentication.config.get('persistence')
            session_result = await authentication.sign_in(**constants)
            if session_result.get('success'):
                session.setdefault('providers', {})
                session.setdefault('user', {})
                session['providers'][authentication.name] = session_result['outputs']['providers'][authentication.name]
                session['user'] = session_result['outputs']['user']
            else:
                return flow.error(session_result['errors'])
            '''if provider_persistence:
                await storekeeper.store(repository='sessions',payload=session)
                pass'''
        return flow.success(session)

    @flow.result(outputs=('session',))
    async def activate(self, session, **constants) -> Any:
        """
        Registra un utente utilizzando i provider configurati.

        :param constants: Deve includere 'identifier', 'ip' e credenziali.
        :return: Dizionario di sessione aggiornato se la registrazione ha successo, altrimenti None.
        """
        for authentication in self.authentications:
            session_result = await authentication.sign_up(user=constants)
            print("----------------->1",session_result)
            if session_result.get('success'):
                session.setdefault('providers', {})
                session.setdefault('user', {})
                session['providers'][authentication.name] = session_result['outputs']['providers'][authentication.name]
                session['user'] |= session_result['outputs']['user']
            else:
                return flow.error(session_result['errors'])
        return flow.success(session)

    def  authorized(self, policy, **constants) -> bool:
        policy = self.get_policy(policy)
        rules = policy.get('rules', {})
        action, resource, location = constants.get('action', ''), constants.get('resource', ''), constants.get('location', '')
        target = {'action':action, 'resource':resource, 'location':location}
        filted_rules = []
        all_resutl = []
        if location in rules:
            filted_rules = rules.get(location)
        elif resource in rules:
            filted_rules = rules.get(resource)
        else:
            pass

        #print("--------------->2",constants)  
        for rule in filted_rules:
            #print("--------------->3",rule)
            for_target = rule.get('target', {}) | target
            #print("--------------->4",for_target)
            condition = rule.get('condition')
            if callable(condition):
                tes = condition(**for_target)
                effect = rule.get('effect')
                if effect == 'allow':
                    all_resutl.append(tes)
                elif effect == 'deny':
                    all_resutl.append(not tes)
            elif isinstance(condition, bool):
                if rule.get('effect') == 'allow':
                    all_resutl.append(condition)
                elif rule.get('effect') == 'deny':
                    all_resutl.append(not condition)
            else:
                all_resutl.append(False)
        return any(all_resutl) if len(all_resutl) > 0 else False

    async def authenticated(self, **constants) -> bool:
        """
        Verifica se una sessione è autenticata.

        :param constants: Deve includere 'session'.
        :return: True se la sessione è valida, altrimenti False.
        """
        session_token = constants.get('session', '')
        return session_token in {session['token'] for session in self.sessions.values()}

    async def authorize(self, **constants) -> bool:
        """
        Controlla se un'azione è autorizzata in base all'indirizzo IP.

        :param constants: Deve includere 'ip'.
        :return: True se l'IP è autorizzato, altrimenti False.
        """
        ip = constants.get('ip', '')
        return any(session.get('ip') == ip for session in self.sessions.values())
    
    async def whoami(self, ip=None, session_id=None) -> Any:
        
        '''for backend in self.providers:
            identity = await backend.whoami(token=constants.get('token', ''))
            return identity'''
        if False:
            pass
        else:
            return {"role":"guest","name":"guest","id":"guest","ip":ip}

    def resolve(self, risorse, request_url, request_method, base_url=None,**kargs):
        
        try:
            # 1. Normalizzazione URL
            # Se request_url è relativo (es. "/home"), urljoin lo unisce a base_url
            full_url = urljoin(base_url, request_url) if base_url else request_url
            parsed = urlparse(full_url)
            
            # Pulizia del path: togliamo slash vuoti per la lista, ma manteniamo il path stringa per il match
            path_list = [p for p in parsed.path.split('/') if p]
            
            # Trasformiamo query e fragment in dizionari puliti
            query_params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}
            frag_params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.fragment).items()}

            url_payload = {
                'url': full_url,
                'protocol': parsed.scheme,
                'host': parsed.hostname,
                'port': parsed.port,
                'path': path_list,
                'query': query_params,
                'fragment': frag_params
            }

            # 2. Ciclo di Matching (Corretto con .values() per evitare TypeError)
            for route_data in risorse.values():
                # Il match va fatto sulla stringa parsed.path
                match = route_data['pattern'].match(parsed.path)
                
                if match:
                    # Recuperiamo i metadati (che contengono 'method', 'view', etc.)
                    metadata = route_data.get('metadata', route_data)
                    
                    # Controllo Metodo HTTP (se presente nei metadati)
                    if metadata.get('method') and metadata['method'] != request_method:
                        continue
                    
                    # Estrazione parametri dinamici dalla Regex (es. {'id': '123'})
                    dynamic_params = match.groupdict()
                    '''authorized = self.defender.authorized('presentation', action=request_method, resource=metadata.get('view'), location=metadata.get('path'))
                    
                    if not authorized:
                        return None'''
                    return {
                        'metadata': metadata,
                        'params': dynamic_params,
                        'url_details': url_payload
                    }

            print(f"[-] No route matched for: {parsed.path}")
            return None

        except Exception as e:
            print(f"[!] Resolve Error: {e}")
            return None

    async def detection(self, **constants) -> bool:
        """
        Placeholder per il rilevamento di minacce.

        :param constants: Parametri opzionali per il rilevamento.
        :return: True come comportamento predefinito.
        """
        return True

    async def protection(self, **constants) -> bool:
        """
        Placeholder per la protezione attiva.

        :param constants: Parametri opzionali per la protezione.
        :return: True come comportamento predefinito.
        """
        return True

    def revoke_session(self, **constants) -> None:
        """
        Placeholder per rimuovere sessioni scadute o non più valide.

        Questo metodo potrebbe essere implementato con controlli di scadenza basati su timestamp.

        :param constants: Parametri opzionali per la pulizia.
        """
        pass

    def refresh_token(self, **constants) -> None:
        """
        Placeholder per rimuovere sessioni scadute o non più valide.

        Questo metodo potrebbe essere implementato con controlli di scadenza basati su timestamp.

        :param constants: Parametri opzionali per la pulizia.
        """
        pass

    def validate_token(self, **constants) -> None:
        """
        Placeholder per rimuovere sessioni scadute o non più valide.

        Questo metodo potrebbe essere implementato con controlli di scadenza basati su timestamp.

        :param constants: Parametri opzionali per la pulizia.
        """
        pass

    async def check_permission(self, **constants) -> bool:
        """
        Verifica se il contesto corrente ha i permessi per eseguire l'azione richiesta.
        
        :param constants: Il contesto dell'esecuzione (deve contenere informazioni scure sull'utente/token/task).
        :return: True se permesso, False altrimenti.
        """
        # Logica di base: se non ci sono regole restrittive, permetti.
        # Qui potresti integrare controlli su ruoli, liste di controllo accessi (ACL), ecc.
        
        # Esempio: Controlla se l'utente è autenticato (se richiesto)
        # if not await self.authenticated(**constants):
        #    return False
        
        # Esempio: Implementazione minima che ritorna True per ora, 
        # ma predisposta per estensioni future.
        return True

    def has_role(self, **constants) -> bool:
        """
        Verifica se l'utente ha uno specifico ruolo.
        """
        user_roles = constants.get('roles', [])
        required_role = constants.get('required_role')
        if required_role and required_role not in user_roles:
            return False
        return True

    def has_permission(self, **constants) -> bool:
        """
        Verifica se l'utente ha uno specifico permesso.
        """
        user_permissions = constants.get('permissions', [])
        required_permission = constants.get('required_permission')
        if required_permission and required_permission not in user_permissions:
            return False
        return True