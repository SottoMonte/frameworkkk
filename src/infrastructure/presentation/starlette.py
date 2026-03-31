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

    attributes = {
        presentation.Attribute.SRC.value:{"img":"src","video":"src","audio":"src","embed":"src","carousel":"src","map":"src","icon":"src"},
        presentation.Attribute.CONTROLS.value:{"video":"controls","audio":"controls"},
        presentation.Attribute.AUTOPLAY.value:{"video":"autoplay","audio":"autoplay"},
        presentation.Attribute.LOOP.value:{"video":"loop","audio":"loop"},
        presentation.Attribute.MUTED.value:{"video":"muted","audio":"muted"},
        presentation.Attribute.TYPE.value:{"app":"type","navigation":"type","embed":"type","input":"type","select":"type","textarea":"type","button":"type","link":"type","img":"type","video":"type","audio":"type","embed":"type","carousel":"type","map":"type","icon":"type"},
        presentation.Attribute.WIDTH.value:{"img":"width","video":"width","audio":"width","embed":"width","carousel":"width","map":"width","icon":"width"},
        presentation.Attribute.HEIGHT.value:{"img":"height","video":"height","audio":"height","embed":"height","carousel":"height","map":"height","icon":"height"},
        presentation.Attribute.ID.value:{"app":"id","window":"id","text":"id","input":"id","select":"id","textarea":"id","button":"id","link":"id","img":"id","video":"id","audio":"id","embed":"id","carousel":"id","map":"id","icon":"id"},
        presentation.Attribute.CLASS.value:{"window":"class","text":"class","input":"class","select":"class","textarea":"class","button":"class","link":"class","img":"class","video":"class","audio":"class","embed":"class","carousel":"class","map":"class","icon":"class"},
        presentation.Attribute.TITLE.value:{"window":"title"},
        presentation.Attribute.NAME.value:{"input":"name","select":"name","textarea":"name","button":"name","link":"name","img":"name","video":"name","audio":"name","embed":"name","carousel":"name","map":"name","icon":"name"},
        presentation.Attribute.VALUE.value:{"input":"value","select":"value","textarea":"value","button":"value","link":"value","img":"value","video":"value","audio":"value","embed":"value","carousel":"value","map":"value","icon":"value"},
        presentation.Attribute.PLACEHOLDER.value:{"input":"placeholder","select":"placeholder","textarea":"placeholder","button":"placeholder","link":"placeholder","img":"placeholder","video":"placeholder","audio":"placeholder","embed":"placeholder","carousel":"placeholder","map":"placeholder","icon":"placeholder"},
        presentation.Attribute.REQUIRED.value:{"input":"required","select":"required","textarea":"required","button":"required","link":"required","img":"required","video":"required","audio":"required","embed":"required","carousel":"required","map":"required","icon":"required"},
        presentation.Attribute.DISABLED.value:{"input":"disabled","select":"disabled","textarea":"disabled","button":"disabled","link":"disabled","img":"disabled","video":"disabled","audio":"disabled","embed":"disabled","carousel":"disabled","map":"disabled","icon":"disabled"},
        presentation.Attribute.READONLY.value:{"input":"readonly","select":"readonly","textarea":"readonly","button":"readonly","link":"readonly","img":"readonly","video":"readonly","audio":"readonly","embed":"readonly","carousel":"readonly","map":"readonly","icon":"readonly"},
        presentation.Attribute.MAX.value:{"input":"max","select":"max","textarea":"max","button":"max","link":"max","img":"max","video":"max","audio":"max","embed":"max","carousel":"max","map":"max","icon":"max"},
        presentation.Attribute.MIN.value:{"input":"min","select":"min","textarea":"min","button":"min","link":"min","img":"min","video":"min","audio":"min","embed":"min","carousel":"min","map":"min","icon":"max"},
        presentation.Attribute.MULTIPLE.value:{"input":"multiple","select":"multiple","textarea":"multiple","button":"multiple","link":"multiple","img":"multiple","video":"multiple","audio":"multiple","embed":"multiple","carousel":"multiple","map":"multiple","icon":"multiple"},
    }

    tags = {
        presentation.Tag.WINDOW.value: {
            "types":{
                "window": lambda x: htpy.html[
                    htpy.head[
                        htpy.meta(charset="utf-8"),
                        htpy.meta(name="viewport", content="width=device-width, initial-scale=1"),
                        htpy.title[x.get("attrs", {}).get("title", "Today's menu")],
                        # Caricamento CSS di Bootstrap 5.3
                        htpy.link(
                            rel="stylesheet", 
                            href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
                        )
                    ],
                    htpy.body(class_="bg-light")[
                        [Markup(i) for i in x['inner']],
                        # Caricamento JS di Bootstrap (necessario per Modal, Dropdown, Accordion)
                        htpy.script(src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js")
                    ]
                ],
                # Rendering del Modal Bootstrap
                "dialog": lambda x: htpy.div(
                    class_="modal fade", 
                    id=x.get("attrs", {}).get("id", "myModal"), # ID fondamentale per il trigger
                    tabindex="-1",
                    aria_hidden="true"
                )[
                    htpy.div(class_="modal-dialog")[
                        htpy.div(class_="modal-content")[
                            # Header del Modal
                            htpy.div(class_="modal-header")[
                                htpy.h5(class_="modal-title")[x.get("attrs", {}).get("title", "")],
                                htpy.button(type="button", class_="btn-close", data_bs_dismiss="modal", aria_label="Close")
                            ],
                            # Corpo del Modal (qui vanno i figli XML)
                            htpy.div(class_="modal-body")[
                                [Markup(i) for i in x['inner']]
                            ],
                            # Footer opzionale (puoi gestirlo con un sotto-tag se vuoi)
                            htpy.div(class_="modal-footer")[
                                htpy.button(type="button", class_="btn btn-secondary", data_bs_dismiss="modal")["Chiudi"]
                            ]
                        ]
                    ]
                ],
                "still": lambda x: htpy.div(
                    class_=f"offcanvas offcanvas-{x.get('attrs', {}).get('alignment-content', 'start')}", 
                    tabindex="-1",
                    id=x.get("attrs", {}).get("id", "offcanvasMenu"),
                    aria_labelledby=f"{x.get('attrs', {}).get('id', 'offcanvasMenu')}Label"
                )[
                    # Header dell'Offcanvas
                    htpy.div(class_="offcanvas-header")[
                        htpy.h5(class_="offcanvas-title", id=f"{x.get('attrs', {}).get('id', 'offcanvasMenu')}Label")[
                            x.get("attrs", {}).get("title", "")
                        ],
                        htpy.button(type="button", class_="btn-close", data_bs_dismiss="offcanvas", aria_label="Close")
                    ],
                    # Body dell'Offcanvas
                    htpy.div(class_="offcanvas-body")[
                        [Markup(i) for i in x['inner']]
                    ]
                ],
            }
        },
        presentation.Tag.TEXT.value: {
            "types":{
                "text":htpy.text,
                "h1": htpy.h1,
                "h2": htpy.h2,
                "h3": htpy.h3,
                "h4": htpy.h4,
                "h5": htpy.h5,
                "h6": htpy.h6,
                "p": htpy.p,
                "span": htpy.span,
                "a": htpy.a,
                "em": htpy.em,
                "mark": htpy.mark,
                "code": htpy.code,
                "pre": htpy.pre,
                "blockquote": htpy.blockquote,
                "q": htpy.q,
                "cite": htpy.cite,
                "abbr": htpy.abbr,
                "time": htpy.time,
            },
            "attributes":{
                "text":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.INPUT.value: {
            "types":{
                "input":htpy.input,
                "select":htpy.select,
                "textarea":htpy.textarea,
                "text":htpy.input(type="text"),
                "password":htpy.input(type="password"),
                "switch":htpy.input(type="checkbox",class_="form-switch"),
                "checkbox":htpy.input(type="checkbox"),
                "radio":htpy.input(type="radio"),
                "range":htpy.input(class_="form-range",type="range"),
                "color":htpy.input(type="color"),
                "date":htpy.input(type="date"),
                "datetime-local":htpy.input(type="datetime-local"),
                "month":htpy.input(type="month"),
                "week":htpy.input(type="week"),
                "time":htpy.input(type="time"),
                "number":htpy.input(type="number"),
                "email":htpy.input(type="email"),
                "url":htpy.input(type="url"),
                "search":htpy.input(type="search"),
                "tel":htpy.input(type="tel"),
                "dropdown":htpy.select(".form-select"),
                "file":htpy.input(type="file")
            },
            "attributes":{
                "input":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.NAME.value,
                    presentation.Attribute.VALUE.value,
                    presentation.Attribute.PLACEHOLDER.value,
                    presentation.Attribute.MAX.value,
                    presentation.Attribute.MIN.value,
                    presentation.Attribute.REQUIRED.value,
                    presentation.Attribute.DISABLED.value,
                    presentation.Attribute.READONLY.value,
                    presentation.Attribute.MULTIPLE.value,
                ]
            }
        },
        presentation.Tag.ACTION.value: {
            "types":{
                "action":htpy.button,
                "button":htpy.button,
                "submit":htpy.submit,
                "reset":htpy.reset,
            },
            "attributes":{
                "action":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.MEDIA.value: {
            "types":{
                "media":htpy.img,
                "img":htpy.img,
                "video":htpy.video,
                "audio":htpy.audio,
                "embed":htpy.embed,
                "carousel":htpy.carousel,
                "map":htpy.map,
                "icon":htpy.icon
            },
            "attributes":{
                "img":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ],
                "video":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.CONTROLS.value,
                    presentation.Attribute.AUTOPLAY.value,
                    presentation.Attribute.LOOP.value,
                    presentation.Attribute.MUTED.value
                ],
                "audio":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.CONTROLS.value,
                    presentation.Attribute.AUTOPLAY.value,
                    presentation.Attribute.LOOP.value,
                    presentation.Attribute.MUTED.value
                ],
                "embed":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ],
                "carousel":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ],
                "map":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ],
                "icon":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.CONTAINER.value: {
            "types":{
                "container":lambda x: htpy.div(".container")[[Markup(i) for i in x['inner']]],
                "fluid":lambda x: htpy.div(".container-fluid")[[Markup(i) for i in x['inner']]],
            },
            "attributes":{
                "container":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.ROW.value: {
            "types":{
                "row":lambda x: htpy.div(".d-flex .flex-row")[[Markup(i) for i in x['inner']]],
            },
            "attributes":{
                "row":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.COLUMN.value: {
            "types":{
                "column":lambda x: htpy.div(".d-flex.flex-column")[[Markup(i) for i in x['inner']]],
            },
            "attributes":{
                "column":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.STACK.value: {
            "types":{
                "stack":lambda x: htpy.div(".position-relative")[[Markup(i) for i in x['inner']]],
            },
            "attributes":{
                "stack":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.DIVIDER.value: {
            "types":{
                "divider":lambda x: htpy.hr,
                "vertical":lambda x: htpy.div(".vr"),
                "horizontal":lambda x: htpy.hr,
            },
            "attributes":{
                "divider":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ]
            }
        },
        presentation.Tag.NAVIGATION.value: {
            "types":{
                "navigation":lambda x: htpy.nav(".navbar")[[Markup(i) for i in x['inner']]],
                "bar":lambda x: htpy.nav(".nav")[[Markup(i) for i in x['inner']]],
                "app":lambda x: htpy.nav(".navbar")[[Markup(i) for i in x['inner']]],
                "breadcrumb":lambda x: htpy.nav(".breadcrumb")[[Markup(i) for i in x['inner']]],
                "tab":lambda x: htpy.nav(".nav-tabs")[[Markup(i) for i in x['inner']]],
            },
            "attributes":{
                "navigation":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.ALT.value,
                    presentation.Attribute.TITLE.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ],
                "bar":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.CONTROLS.value,
                    presentation.Attribute.AUTOPLAY.value,
                    presentation.Attribute.LOOP.value,
                    presentation.Attribute.MUTED.value
                ],
                "breadcrumb":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.CONTROLS.value,
                    presentation.Attribute.AUTOPLAY.value,
                    presentation.Attribute.LOOP.value,
                    presentation.Attribute.MUTED.value
                ],
                "app":[
                    presentation.Attribute.TYPE.value,
                    presentation.Attribute.SRC.value,
                    presentation.Attribute.WIDTH.value,
                    presentation.Attribute.HEIGHT.value
                ],
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
        return await self.builder(file=matched_route['view'], url=url_payload, mode=['main'], identifier=kargs.get('identifier'))

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
            return tag({"inner": inner, "attrs": attrs})
        # Altrimenti trattalo come un elemento htpy standard
        children = [Markup(i) for i in inner] if isinstance(inner, list) else Markup(inner or "")
        if not hasattr(tag, "__getitem__"):
            return tag(**attrs)
        return str(tag(**attrs)[children])
    
    def node_union(self, node, context):
        pass
    
    def node_update(self, node, context):
        pass