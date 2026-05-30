import asyncio
import uuid
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List


from textual.app import App, ComposeResult
from textual.containers import Container, HorizontalGroup, Vertical
from textual.widgets import Link, Checkbox, Static, Button, Input, Select, TextArea, Header, Footer, Label, Markdown
from rich.text import Text
from textual.screen import Screen
from textual.binding import Binding

def attrs(widget,attrs):
    '''for k,v in attrs.items():
        setattr(widget, k, v)'''
    widget.styles.overflow_y = "auto"
    widget.styles.overflow_x = "hidden"

    # 3. Se necessario, gli dai una dimensione bloccata o flessibile
    widget.styles.height = "80%"  # oppure "1fr"
    return widget

class XmlScreen(Screen):
    """Una schermata che si auto-costruisce leggendo un file XML."""
    
    def __init__(self, inner: str, title: str, sub_title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.inner = inner
        self.title = title
        self.sub_title = sub_title

    def compose(self) -> ComposeResult:   

        yield Header()

        # 3. Generiamo ricorsivamente i widget figli
        #for child in root:
        #    yield from self.renderizza_nodo(child)

        print(self.inner)

        yield Container(*self.inner)

        yield Footer()

class AppDinamica(App):
    BINDINGS = [
        ("d", "toggle_dark", "Cambia Tema"),
        ("q", "quit", "Esci")
    ]

    def __init__(self, adapter, **kwargs):
        super().__init__(**kwargs)
        self.adapter = adapter

    async def on_mount(self) -> None:
        await self.adapter.render_view(url="/")


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id:
            return None

        widget = self.DOM[event.button.id]


        
        print(f"Button {event.button.id} premuto!")

class Adapter(presentation.port):
    """
    Adapter Textual nativo per il Framework
    
    Implementa la stessa interfaccia di presentation.port come starlette.server.Adapter
    Riceve le dipendenze via injection dal container (defender, messenger, executor, presenter)
    """
    
    tags = {
        presentation.Tag.ICON.value: { 
            "icon": lambda x: Static(*x.get('inner',[]), id="ciao"),
        },
        presentation.Tag.COLUMN.value: { 
            "column": lambda x: Vertical(*x.get('inner',[])),
        },
        presentation.Tag.ROW.value: { 
            "row": lambda x: HorizontalGroup(*x.get('inner',[])),
        },
        presentation.Tag.ACTION.value: { 
            "link": lambda x: Link(str(x.get('inner',[''])[0]),url=x.get('attrs', {}).get('href', '#')),
            "button": lambda x: Button(str([ f.render() for f in x.get('inner',[]) if not isinstance(f, str)]), id="button"),
        },
        presentation.Tag.INPUT.value: { 
            "select": lambda x: Select([(str(i.render()),0) if type(i) != str else (i,0) for i in x.get('inner',[])]),
            "text":  lambda x: TextArea(),
            "input": lambda x: Input(placeholder=x.get('attrs', {}).get('placeholder', '')),
            "checkbox": lambda x: Checkbox(str(x.get('inner',[''])[0])),
            "masked": lambda x: MaskedInput(template=x.get('attrs', {}).get('placeholder', '')),
            "option": lambda x: OptionList(*x.get('inner',[])),
            "switch": lambda x: Switch(str(x.get('inner',[''])[0])),
        },
        presentation.Tag.TEXT.value: {
            "text": lambda x: Label(Text(*x.get('inner',''))),
            "markdown": lambda x: attrs(Markdown(*x.get('inner','')), x.get('attrs', {})),
            "pretty": lambda x: Pretty(*x.get('inner',[])),
        },
        presentation.Tag.NAVIGATION.value: {
            "navigation": lambda x: Static(*x.get('inner',[]), id="nav")
        },
        presentation.Tag.WINDOW.value: {
            "window": lambda x: XmlScreen([f for f in x.get('inner',[]) if not isinstance(f, str)], x.get('attrs', {}).get('title', 'App'), x.get('attrs', {}).get('subtitle', ''))
        },
        presentation.Tag.GROUP.value: {
            "list": lambda x: ListView(*[ListItem(f) for f in x.get('inner',[])]),
            "tab": lambda x: Tabs(*[Tab(f, title=f.get('attrs', {}).get('title', 'Tab')) for f in x.get('inner',[])])
        },
        presentation.Tag.DIVIDER.value: {
            "horizontal": lambda x: Rule(),
        }
    }


    def __init__(self, **constants):
        """
        Inizializza l'adapter Textual
        
        Args (via dependency injection dal container):
            defender: Manager per autenticazione/autorizzazione
            messenger: Manager per messaggistica
            executor: Manager per esecuzione DSL
            presenter: Manager per presentazione
            **constants: Configurazione da pyproject.toml (adapter.registry)
        """
        self.config = constants
        self.messenger = constants.get('messenger')
        self.defender = constants.get('defender')
        self.executor = constants.get('executor')
        self.presenter = constants.get('presenter')
        self.initialize()
        # Stato TUI
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.active_screens: Dict[str, 'TUIScreen'] = {}
        self.app = AppDinamica(self)
    
    async def start(self):
        """
        Avvia l'applicazione TUI
        Equivalente di Starlette server.serve()
        
        Returns:
            Coroutine per esecuzione async
        """

        # Restituisci il coroutine di esecuzione (come fa Starlette)
        await self.parse_route()
        return self.app.run_async()
    
    def mount_css(self, css_content: str) -> None:
        """
        Inietta lo stile nell'applicazione.
        Nel web mappa su un file CSS. In Textual, carichiamo le regole nel foglio di stile dell'App.
        """
        if self.app:
            # Textual permette di iniettare stringhe CSS dinamicamente
            self.app.parse_stylesheet(css_content)

    async def mount_view(self,url):
        xml_view = await presentation.loader.resource(self.routes['/']['GET']['view'])
        return await self.render_template(text=xml_view)

    async def render_view(self,url):
        print("Mounting view...",self.routes)
        screen = await self.mount_view(url=url)
        self.app.push_screen(screen)
    
    async def mount_route(self, routes):
        for path, methods_dict in self.routes.items():
            for method, data in methods_dict.items():
                typee = data.get('type')
                # method = data.get('method')
                view = data.get('view')

                # Associa il path alla view (utile per debug o reverse lookup)
                self.views[path] = view

                #routes.append(r)

    async def authenticate(self, session: Dict[str, Any], **credentials) -> Dict[str, Any]:
        """
        Autentica un utente
        Delegato al defender manager
        """
        if self.defender:
            return await self.defender.authenticate(session, **credentials)
        return {"success": False, "errors": ["Autenticazione non disponibile"]}
    
    async def terminate(self, session: Dict[str, Any], **credentials) -> Dict[str, Any]:
        """
        Termina una sessione
        Delegato al defender manager
        """
        if self.defender:
            return await self.defender.terminate(session, **credentials)
        return {"success": True}
    
    async def activate(self, session: Dict[str, Any], **credentials) -> Dict[str, Any]:
        """
        Attiva un nuovo account
        Delegato al defender manager
        """
        if self.defender:
            return await self.defender.activate(session, **credentials)
        return {"success": False, "errors": ["Attivazione non disponibile"]}
    
    async def rebuild(self, session: Dict[str, Any], **credentials):
        pass

    async def render_reactive(self, session, view: Any, context) -> Any:
        file_path = f"src/application/controller/{dsl_alias}.dsl"
        content = await presentation.loader.resource(file_path)
        await self.executor.add_file(file_path, content)
        self.executor.interpreter.runner.emit(sid, file_path, event_name)
    
    def node_create(self, tag, attrs={}, inner=[]):
        #inner =  [f for f in inner if not isinstance(f, str) and tag == ]
        # Se tag è una funzione (es. un componente funzionale/lambda)
        if callable(tag) and type(tag).__name__ == "function":
            return tag({"inner": inner, "attrs": attrs})
        # Altrimenti trattalo come un elemento htpy standard
        #children = [Markup(i) for i in inner] if isinstance(inner, list) else Markup(inner or "")
        raise NotImplementedError("node_create è stato deprecato. Usa node_create2 per creare widget Textual direttamente da tag DSL.")

    def node_union(self, node, context: Dict[str, Any]):
        """
        Unisce nodi DSL con contesto
        Implementa l'interfaccia di presentation.port
        """
        return node
    
    def node_update(self, node, context: Dict[str, Any]):
        """
        Aggiorna nodi con nuovo contesto
        Implementa l'interfaccia di presentation.port
        """
        return node