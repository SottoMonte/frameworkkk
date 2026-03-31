import uuid
import asyncio
from html import escape
import re
import json
from datetime import datetime
from urllib.parse import urlparse, urlunparse, ParseResult,parse_qs
import htpy
from markupsafe import Markup

try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse,HTMLResponse,RedirectResponse
    from starlette.routing import Route,Mount,WebSocketRoute
    from starlette.middleware import Middleware
    from starlette.websockets import WebSocket
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
    #from starlette.middleware.csrf import CSRFMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.staticfiles import StaticFiles

    import os
    import uuid
    #import uvicorn
    from uvicorn import Config, Server

    # Auth 
    #from starlette.middleware.sessions import SessionMiddleware
    from datetime import timedelta
    import secrets
    #from starlette_login.middleware import AuthenticationMiddleware

    #
    from starlette.requests import HTTPConnection
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from starlette.datastructures import MutableHeaders
    import http.cookies
    import markupsafe
    from bs4 import BeautifulSoup
    import paramiko
    import asyncio

    '''class NoCacheMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Server"] = "Starlette-Test"
            return response'''

except Exception as e:
    #import starlette
    import markupsafe
    from bs4 import BeautifulSoup
    
    import xml.etree.ElementTree as ET
    from xml.sax.saxutils import escape

class Adapter(presentation.port):

    # --- Configurazione Programmatica Attributi ---
    _A = presentation.Attribute
    _CORE = {a.value: a.value for a in [_A.ID, _A.CLASS, _A.TITLE]}
    _MEDIA = {**_CORE, **{a.value: a.value for a in [_A.SRC, _A.WIDTH, _A.HEIGHT, _A.ALT]}}
    _FIELD = {**_CORE, **{a.value: a.value for a in [_A.NAME, _A.VALUE, _A.PLACEHOLDER, _A.REQUIRED, _A.DISABLED, _A.READONLY, _A.MAX, _A.MIN, _A.MULTIPLE, _A.TYPE]}}
    _MULTIMEDIA = {**_MEDIA, **{a.value: a.value for a in [_A.CONTROLS, _A.AUTOPLAY, _A.LOOP, _A.MUTED]}}

    _ATTR_SCHEMA = {
        "window": _CORE, "text": _MEDIA, "input": _FIELD, "select": _FIELD, "textarea": _FIELD, 
        "action": _MEDIA, "button": _CORE, "submit": _CORE, "img": _MEDIA, "video": _MULTIMEDIA, 
        "audio": _MULTIMEDIA, "embed": _MEDIA, "carousel": _MEDIA, "map": _MEDIA, "icon": _MEDIA,
        "container": _MEDIA, "row": _MEDIA, "column": _MEDIA, "stack": _MEDIA, "divider": _MEDIA,
        "navigation": _MEDIA, "bar": _MULTIMEDIA, "app": _MEDIA, "breadcrumb": _MULTIMEDIA, "tab": _MEDIA
    }

    attributes = {}
    for _tag, _attrs in _ATTR_SCHEMA.items():
        for _attr_key, _html_name in _attrs.items():
            attributes.setdefault(_attr_key, {})[_tag] = _html_name

    # --- Configurazione Tag ---
    tags = {
        presentation.Tag.WINDOW.value: {
            "types": {
                "window": lambda x: htpy.html[
                    htpy.head[
                        htpy.meta(charset="utf-8"),
                        htpy.meta(name="viewport", content="width=device-width, initial-scale=1"),
                        htpy.title[x.get("attrs", {}).get("title", "Today's menu")],
                        htpy.link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css")
                    ],
                    htpy.body(class_="bg-light")[
                        [Markup(i) for i in x['inner']],
                        htpy.script(src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js")
                    ]
                ],
                "dialog": lambda x: htpy.div(class_="modal fade", id=x.get("attrs", {}).get("id", "myModal"), tabindex="-1", aria_hidden="true")[
                    htpy.div(class_="modal-dialog")[
                        htpy.div(class_="modal-content")[
                            htpy.div(class_="modal-header")[
                                htpy.h5(class_="modal-title")[x.get("attrs", {}).get("title", "")],
                                htpy.button(type="button", class_="btn-close", data_bs_dismiss="modal", aria_label="Close")
                            ],
                            htpy.div(class_="modal-body")[[Markup(i) for i in x['inner']]],
                            htpy.div(class_="modal-footer")[
                                htpy.button(type="button", class_="btn btn-secondary", data_bs_dismiss="modal")["Chiudi"]
                            ]
                        ]
                    ]
                ],
                "still": lambda x: htpy.div(class_=f"offcanvas offcanvas-{x.get('attrs', {}).get('alignment-content', 'start')}", tabindex="-1", id=x.get('attrs', {}).get('id', 'offcanvasMenu'), aria_labelledby=f"{x.get('attrs', {}).get('id', 'offcanvasMenu')}Label")[
                    htpy.div(class_="offcanvas-header")[
                        htpy.h5(class_="offcanvas-title", id=f"{x.get('attrs', {}).get('id', 'offcanvasMenu')}Label")[x.get("attrs", {}).get("title", "")],
                        htpy.button(type="button", class_="btn-close", data_bs_dismiss="offcanvas", aria_label="Close")
                    ],
                    htpy.div(class_="offcanvas-body")[[Markup(i) for i in x['inner']]]
                ],
            }
        },
        presentation.Tag.TEXT.value: {
            "types": {
                "text": lambda x: htpy.span()[[Markup(i) for i in x['inner']]],
                "h1": lambda x: htpy.h1()[[Markup(i) for i in x['inner']]],
                "h2": lambda x: htpy.h2()[[Markup(i) for i in x['inner']]],
                "h3": lambda x: htpy.h3()[[Markup(i) for i in x['inner']]],
                "h4": lambda x: htpy.h4()[[Markup(i) for i in x['inner']]],
                "h5": lambda x: htpy.h5()[[Markup(i) for i in x['inner']]],
                "h6": lambda x: htpy.h6()[[Markup(i) for i in x['inner']]],
                "p": lambda x: htpy.p()[[Markup(i) for i in x['inner']]],
                "span": lambda x: htpy.span()[[Markup(i) for i in x['inner']]],
                "a": lambda x: htpy.a()[[Markup(i) for i in x['inner']]],
                "em": lambda x: htpy.em()[[Markup(i) for i in x['inner']]],
                "mark": lambda x: htpy.mark()[[Markup(i) for i in x['inner']]],
                "code": lambda x: htpy.code()[[Markup(i) for i in x['inner']]],
                "pre": lambda x: htpy.pre()[[Markup(i) for i in x['inner']]],
                "blockquote": lambda x: htpy.blockquote()[[Markup(i) for i in x['inner']]],
                "q": lambda x: htpy.q()[[Markup(i) for i in x['inner']]],
                "cite": lambda x: htpy.cite()[[Markup(i) for i in x['inner']]],
                "abbr": lambda x: htpy.abbr()[[Markup(i) for i in x['inner']]],
                "time": lambda x: htpy.time()[[Markup(i) for i in x['inner']]],
            }
        },
        presentation.Tag.INPUT.value: {
            "types": {
                "input": lambda x: htpy.input(type="text", class_="form-control"), 
                "select": lambda x: htpy.select(class_="form-select"), 
                "textarea": lambda x: htpy.textarea(class_="form-control"),
                "text": lambda x: htpy.input(type="text", class_="form-control"), 
                "password": lambda x: htpy.input(type="password", class_="form-control"),
                "switch": lambda x: htpy.input(type="checkbox", class_="form-switch"), 
                "checkbox": lambda x: htpy.input(type="checkbox", class_="form-check-input"),
                "radio": lambda x: htpy.input(type="radio", class_="form-check-input"), 
                "range": lambda x: htpy.input(class_="form-range", type="range"),
                "color": lambda x: htpy.input(type="color", class_="form-control"), 
                "date": lambda x: htpy.input(type="date", class_="form-control"), 
                "month": lambda x: htpy.input(type="month", class_="form-control"), 
                "week": lambda x: htpy.input(type="week", class_="form-control"), 
                "time": lambda x: htpy.input(type="time", class_="form-control"),
                "number": lambda x: htpy.input(type="number", class_="form-control"), 
                "email": lambda x: htpy.input(type="email", class_="form-control"), 
                "url": lambda x: htpy.input(type="url", class_="form-control"),
                "search": lambda x: htpy.input(type="search", class_="form-control"),
                "tel": lambda x: htpy.input(type="tel", class_="form-control"), 
                "dropdown": lambda x: htpy.select(class_="form-select"),
                "file": lambda x: htpy.input(type="file", class_="form-control"),
                "hidden": lambda x: htpy.input(type="hidden"),
            }
        },
        presentation.Tag.ACTION.value: {
            "types": {
                "action": lambda x: htpy.button(type="button", class_="btn btn-primary")[[Markup(i) for i in x['inner']]], 
                "button": lambda x: htpy.button(type="button", class_="btn btn-primary")[[Markup(i) for i in x['inner']]], 
                "submit": lambda x: htpy.input(type="submit", class_="btn btn-primary")[[Markup(i) for i in x['inner']]], 
                "reset": lambda x: htpy.input(type="reset", class_="btn btn-secondary")[[Markup(i) for i in x['inner']]],
            }
        },
        presentation.Tag.MEDIA.value: {
            "types": {
                "media": lambda x: htpy.img, 
                "img": lambda x: htpy.img, 
                "video": lambda x: htpy.video, 
                "audio": lambda x: htpy.audio, 
                "embed": lambda x: htpy.embed, 
                "carousel": lambda x: htpy.div(".carousel"), 
                "map": lambda x: htpy.div(".map"), 
                "icon": lambda x: htpy.i(".bi")
            }
        },
        presentation.Tag.CONTAINER.value: {
            "types": {
                "container": lambda x: htpy.div(".container")[[Markup(i) for i in x['inner']]], 
                "fluid": lambda x: htpy.div(".container-fluid")[[Markup(i) for i in x['inner']]]
            } 
        },
        presentation.Tag.ROW.value: { 
            "types": {
                "row": lambda x: htpy.div(".row")[[Markup(i) for i in x['inner']]]
            } 
        },
        presentation.Tag.COLUMN.value: { 
            "types": {
                "column": lambda x: htpy.div(".col")[[Markup(i) for i in x['inner']]]
            } 
        },
        presentation.Tag.STACK.value: { 
            "types": {
                "stack": lambda x: htpy.div(".position-relative")[[Markup(i) for i in x['inner']]]
            } 
        },
        presentation.Tag.DIVIDER.value: { 
            "types": {
                "divider": lambda x: htpy.hr, 
                "vertical": lambda x: htpy.div(".vr"), 
                "horizontal": lambda x: htpy.hr
            } 
        },
        presentation.Tag.NAVIGATION.value: {
            "types": {
                "navigation": lambda x: htpy.nav(".navbar")[[Markup(i) for i in x['inner']]],
                "bar": lambda x: htpy.nav(".nav")[[Markup(i) for i in x['inner']]],
                "app": lambda x: htpy.nav(".navbar")[[Markup(i) for i in x['inner']]],
                "breadcrumb": lambda x: htpy.nav(".breadcrumb")[[Markup(i) for i in x['inner']]],
                "tab": lambda x: htpy.nav(".nav-tabs")[[Markup(i) for i in x['inner']]],
            }
        },
    }

    def __init__(self,**constants):
        self.config = constants
        self.messenger = constants.get('messenger')
        self.defender = constants.get('defender')
        self.views = dict({})
        self.ssh = {}
        cwd = os.getcwd()
        self.initialize()
        self.routes_static=[
            Mount('/static', app=StaticFiles(directory=f'{cwd}/public/'), name="static"),
            Mount('/framework', app=StaticFiles(directory=f'{cwd}/src/framework'), name="y"),
            Mount('/application', app=StaticFiles(directory=f'{cwd}/src/application'), name="z"),
            Mount('/infrastructure', app=StaticFiles(directory=f'{cwd}/src/infrastructure'), name="x"),
            #WebSocketRoute("/messenger", self.websocket, name="messenger"),
            #WebSocketRoute("/ssh", self.websocketssh, name="ssh"),
        ]
        
        self.middleware_static = [
            Middleware(SessionMiddleware, session_cookie="session_state",secret_key=self.config.get('project',{}).get('key', 'default_key')),
            Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'], allow_credentials=True),
            #Middleware(NoCacheMiddleware),
            #Middleware(CSRFMiddleware, secret=self.config['project']['key']),
            #Middleware(AuthorizationMiddleware, manager=defender)
        ]

    async def start(self):
        loop = asyncio.get_event_loop()
        print("Starlette: Inizializzazione in corso...")
        await self.parse_route()
        self.mount_route(self.routes_static) # 'routes' deve essere accessibile qui
        # Inizializza l'applicazione Starlette con rotte e middleware
        self.app = Starlette(debug=True, routes=self.routes_static, middleware=self.middleware_static)
        #print(di['message'][0].logger,'###########')
        # Parametri di configurazione base per Uvicorn
        uvicorn_config_params = {
            "app": self.app,
            "host": self.config.get('host', '127.0.0.1'),
            "port": int(self.config.get('port', 8000)),
            "use_colors": True,
            "reload": False, # `reload=True` non è compatibile con create_task in questo modo
            "loop": loop,
            #'log_level':"trace"
            #'log_config':None
        }
        # Aggiunge i parametri SSL se presenti
        if 'ssl_keyfile' in self.config and 'ssl_certfile' in self.config:
            #await messenger.post(domain='debug', message="SSL abilitato.")
            uvicorn_config_params['ssl_keyfile'] = self.config['ssl_keyfile']
            uvicorn_config_params['ssl_certfile'] = self.config['ssl_certfile']
        else:
            #await messenger.post(domain='debug', message="SSL disabilitato.")
            pass

        # Costruisci la stringa della porta
        port_str = ""
        if 'port' in uvicorn_config_params:
            port_str = f":{uvicorn_config_params['port']}"

        # Costruisci l'URL
        self.url = f"http{'s' if 'ssl_certfile' in self.config else ''}://{uvicorn_config_params['host']}{port_str}"
        try:
            # Crea e avvia il server Uvicorn come task asyncio
            config = Config(**uvicorn_config_params)
            server = Server(config)
            await server.serve()
            #await messenger.post(domain='debug', message=f"Server avviato su {uvicorn_config_params['host']}:{uvicorn_config_params['port']}")
        except Exception as e:
            # Logga errori critici all'avvio del server
            #await messenger.post(domain='error', message=f"Errore critico durante l'avvio del server Uvicorn: {e}")
            pass
        
    async def logout(self,request,defender) -> None:
        assert request.scope.get("app") is not None, "Invalid Starlette app"
        request.session.clear()
        response = RedirectResponse('/', status_code=303)
        response.delete_cookie("session_token")
        return response

    async def login(self, request):
        """Gestisce il login dell'utente con autenticazione basata su IP e sessione."""
        
        client_ip = request.client.host
        session_identifier = request.cookies.get('session_identifier', secrets.token_urlsafe(16))
        url_precedente = request.session.get("url_precedente",request.url)
        
        # Determina le credenziali in base al metodo HTTP
        if request.method == 'GET':
            credentials = dict(request.query_params)
        elif request.method == 'POST':
            credentials = dict(await request.form())
        else:
            return RedirectResponse('/', status_code=405)

        # Autenticazione tramite defender
        session = await self.defender.authenticate(storekeeper,ip=client_ip, identifier=session_identifier, **credentials)
        provider = credentials.get('provider', 'undefined')
        
        # Aggiorna la sessione se l'autenticazione ha avuto successo
        #if session:
        #    request.session.update(session)

        # Crea la risposta di reindirizzamento
        response = RedirectResponse(url_precedente, status_code=303)
        # Imposta i cookie della sessione se non già presenti
        if 'session_identifier' not in request.cookies:
            response.set_cookie(key='session_identifier', value=session_identifier)
        
        #response.set_cookie(key='session', value=token, max_age=3600)
        response.set_cookie(key='session', value=session)
        
        #await messenger.post(domain=f"error.{client_ip}",message=f"🔑 Login completato per IP: {client_ip} | con provider: {provider} | Session: {session_identifier}")

        return response

    async def websocket(self, websocket):
        ip = websocket.client.host
        await websocket.accept()
        #await messenger.post(domain='info', message=f"🔌 Connessione WebSocket da {ip}")

        #ws_queue = asyncio.Queue()  # Coda per i messaggi WebSocket
        #messenger_queue = asyncio.Queue()  # Coda per i messaggi di Messenger
        stop_event = asyncio.Event()  # Evento per fermare il loop quando necessario

        async def listen_websocket():
            try:
                while not stop_event.is_set():
                    msg = await websocket.receive_text()
                    #await messenger.post(domain='debug', message=f"📥 Messaggio dal client: {msg}")
                    await websocket.send_text(msg)
            except Exception:
                stop_event.set()  # Ferma il ciclo se il WebSocket si chiude

        async def listen_for_updates():
            while not stop_event.is_set():
                msg = await messenger.read(domain='*',identity=ip)
                #await messenger.post(domain='debug', message=f"📨 Messaggio dal server: {msg}")
                #await messenger_queue.put(msg)
                await websocket.send_text(msg)
    
    async def websocketssh(self, websocket):
        ip = websocket.client.host

        # Sessione di autenticazione
        session = await self.defender.whoami(ip=ip)
        await websocket.accept()

        try:
            # Riceve parametri iniziali
            initial_message = await websocket.receive_text()
            #await messenger.post(domain='debug', message=f"Sessione {session} con messaggio iniziale: {initial_message}")
            params = json.loads(initial_message)
            username = params.get("username")
            password = params.get("password")
            host = params.get("host")

            # Connessione SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password)
            channel = ssh.invoke_shell()

            # Invia la risposta iniziale del terminale (banner, prompt, ecc.)
            if channel.recv_ready():
                initial_response = channel.recv(1024).decode('utf-8')
                await websocket.send_text(initial_response)

            # Lettura dati da SSH → WebSocket
            async def read_from_channel():
                while True:
                    if websocket.client_state.name != "CONNECTED":
                        break
                    if channel.recv_ready():
                        data = channel.recv(1024).decode('utf-8')
                        await websocket.send_text(data)
                    await asyncio.sleep(0.01)

            # Lettura dati da WebSocket → SSH
            async def read_from_websocket():
                while True:
                    data = await websocket.receive_text()
                    if data:
                        channel.send(data)

            await asyncio.gather(read_from_channel(), read_from_websocket())

        except Exception as e:
            #await self.messenger.post(domain='error', message=f"Errore durante la sessione SSH-WebSocket: {e}")
            pass
        finally:
            try:
                if channel:
                    channel.close()
                if ssh:
                    ssh.close()
                #await self.messenger.post(domain='debug', message=f"Sessione SSH chiusa per {session}")
            except Exception as close_err:
                #await self.messenger.post(domain='error', message=f"Errore durante la chiusura SSH: {close_err}")
                pass
    
    async def action(self, request, storekeeper, messenger, **constants):
        #print(request.cookies.get('user'))
        match request.method:
            case 'GET':
                query = dict(request.query_params)
                #await messenger.post(identifier=id,name=request.url.path[1:],value=dict(query))
                #data = await messenger.get(identifier=id,name=request.url.path[1:],value=dict(query))
                #import application.action.gather as gather
                
                data = await gather.gather(messenger,storekeeper,model=query['model'],payload=query)
                return JSONResponse(data)
                
            case 'POST':
                form = await request.form()
                data = dict(form)
                
                request.scope["user"] = data
                #await messenger.post(name=request.url.path[1:],value={'model':data['model'],'value':data})
                return RedirectResponse('/', status_code=303)

    async def render_view(self,request):
        request.session["url_precedente"] = str(request.url)
        html = await self.mount_view(str(request.url),identifier = request.cookies.get('session_identifier', secrets.token_urlsafe(16)))
        return HTMLResponse(html)

    async def mount_view(self, url,**kargs):
        def process_url(url, default_base_url):
            """
            Unisce raw_url con default_base_url per completare scheme/netloc/etc. usa _replace()
            """
            base = urlparse(default_base_url)
            parsed = urlparse(url)

            merged = parsed._asdict()  # scheme, netloc, path, params, query, fragment
            for field in base._fields:
                if not merged.get(field):          # se vuoto -> copia dal base
                    merged[field] = getattr(base, field)

            return parsed._replace(**merged)
        parsed_url = process_url(url, self.url)   # self.url = base url

        matched_route = None

        for route_path, route_data in self.routes.items():
            # costruiamo il pattern regex in modo sicuro:
            parts = []
            last_idx = 0
            param_names = []

            # trova tutte le {...} nel route_path
            for m in re.finditer(r'\{([^}]+)\}', route_path):
                # escape della parte statica prima della match
                parts.append(re.escape(route_path[last_idx:m.start()]))
                # gruppo di cattura per quel segmento
                parts.append('([^/]+)')
                # salva il nome del parametro, rimuovendo eventuale '$' iniziale
                param_names.append(m.group(1).lstrip('$'))
                last_idx = m.end()

            # aggiungi la parte finale (escaped)
            parts.append(re.escape(route_path[last_idx:]))
            regex_pattern = '^' + ''.join(parts) + '$'

            match = re.search(regex_pattern, parsed_url.path)
            if match:
                matched_route = {
                    'view': route_data.get('view'),
                    'params': {},
                    'layout': route_data.get('layout')
                }

                for i, name in enumerate(param_names):
                    matched_route['params'][name] = match.group(i + 1)

                break  # prima corrispondenza -> esci

        if not matched_route:
            #await messenger.post(domain='debug', message=f"Nessuna rotta corrispondente per l'URL: {url}")
            return None

        # log (opzionale)
        #await messenger.post(domain='debug', message=f"Percorso trovato: {matched_route['view']} per l'URL: {url}")
        #await messenger.post(domain='debug', message=f"Parametri estratti: {matched_route['params']}")

        # parametri query e fragment come dict di liste
        query_params = parse_qs(parsed_url.query, keep_blank_values=True)
        frag_params = parse_qs(parsed_url.fragment, keep_blank_values=True)

        # path come lista di segmenti (evita elemento vuoto se path è '/')
        stripped = parsed_url.path.lstrip('/')
        path_list = stripped.split('/') if stripped else []

        url_payload = {
            'url': self.url,
            'protocol': parsed_url.scheme,
            'host': parsed_url.hostname,
            'port': parsed_url.port,
            'path': path_list,
            'query': query_params,
            'fragment': frag_params
        }

        # chiama il modello / builder come nel tuo flusso
        #url_payload = await language.normalize(url_payload,scheme_url)
        return await self.render_template(file=matched_route['view'], url=url_payload, mode=['main'], identifier=kargs.get('identifier'))

    def mount_route(self, routes):
        for path, data in self.routes.items():
            typee = data.get('type')
            method = data.get('method')
            view = data.get('view')

            # Associa il path alla view (utile per debug o reverse lookup)
            self.views[path] = view

            # Se è una mount statica
            if typee == 'mount' and path == '/static':
                r = Mount(path, app=StaticFiles(directory='/public'), name="static")
                routes.append(r)
                continue

            # Determina l'endpoint
            if typee == 'model':
                endpoint = self.model
            elif typee == 'view':
                endpoint = self.render_view
            elif typee == 'action':
                endpoint = self.action
            elif typee == 'login':
                endpoint = self.login
            elif typee == 'logout':
                endpoint = self.logout
            else:
                endpoint = self.default_handler  # fallback o gestione errori

            # Crea la rotta e aggiungila
            r = Route(path, endpoint=endpoint, methods=[method])
            routes.append(r)

    def mount_css(self, node, context):
        pass

    def node_create(self, tag, attrs={}, inner=[]):
        # Se tag è una funzione (es. un componente funzionale/lambda)
        if callable(tag) and type(tag).__name__ == "function":
            return str(tag({"inner": inner, "attrs": attrs}))
        # Altrimenti trattalo come un elemento htpy standard
        children = [Markup(i) for i in inner] if isinstance(inner, list) else Markup(inner or "")
        if not hasattr(tag, "__getitem__"):
            return str(tag(**attrs))
        return str(tag(**attrs)[children])
    
    def node_union(self, node, context):
        pass
    
    def node_update(self, node, context):
        pass