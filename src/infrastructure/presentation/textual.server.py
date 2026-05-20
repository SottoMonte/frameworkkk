import asyncio
import uuid
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List


from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button, Input, Select, TextArea, Header, Footer
from textual.screen import Screen
from textual.binding import Binding
import xml.etree.ElementTree as ET

class XmlScreen(Screen):
    """Una schermata che si auto-costruisce leggendo un file XML."""
    
    def __init__(self, xml_code: str, **kwargs):
        super().__init__(**kwargs)
        self.xml_code = xml_code
        # Dizionario di mappatura: associa il tag XML alla classe Textual
        self.MAPPATURA_TAG = {
            "text": Static,
            "button": Button,
            "row": Horizontal,
            "column": Vertical
        }

    def compose(self) -> ComposeResult:
        # 1. Parsiamo il file XML
        tree = ET.fromstring(self.xml_code)
        root = tree

        # 2. Gestiamo il tag radice <window> per configurare la schermata
        if root.tag == "window":
            self.title = root.attrib.get("title", "App")
            self.sub_title = root.attrib.get("subtitle", "")

        yield Header()

        # 3. Generiamo ricorsivamente i widget figli
        for child in root:
            yield from self.renderizza_nodo(child)

        yield Footer()

    def renderizza_nodo(self, nodo: ET.Element):
        """Trasforma un nodo XML nel rispettivo Widget di Textual."""
        tag = nodo.tag.lower()
        
        # Recuperiamo gli attributi comuni
        node_id = nodo.attrib.get("id")
        variant = nodo.attrib.get("variant", "default")
        
        # Se il tag è mappato a un contenitore (es. row -> Horizontal)
        if tag in ("row", "column"):
            classe_contenitore = self.MAPPATURA_TAG[tag]
            # Creiamo il contenitore e inseriamo ricorsivamente i suoi figli
            figli_widget = []
            for child in nodo:
                figli_widget.extend(list(self.renderizza_nodo(child)))
            
            yield classe_contenitore(*figli_widget, id=node_id)
            
        # Se è un widget singolo (es. button o text)
        elif tag in self.MAPPATURA_TAG:
            classe_widget = self.MAPPATURA_TAG[tag]
            testo_interno = nodo.text.strip() if nodo.text else ""
            
            if classe_widget == Button:
                yield Button(testo_interno, id=node_id, variant=variant)
            elif classe_widget == Static:
                yield Static(testo_interno, id=node_id)

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
        """Gestiamo i click dei bottoni generati dall'XML sfruttando i loro ID."""
        if event.button.id == "btn_salva":
            self.query_one("#messaggio", Static).update("Dati Salvati con Successo! 🎉")
        elif event.button.id == "btn_cancella":
            self.query_one("#messaggio", Static).update("Azione Annullata. ❌")

class Adapter(presentation.port):
    """
    Adapter Textual nativo per il Framework
    
    Implementa la stessa interfaccia di presentation.port come starlette.server.Adapter
    Riceve le dipendenze via injection dal container (defender, messenger, executor, presenter)
    """
    
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
        return XmlScreen(xml_view)

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

    async def render_reactive(self, session: Dict[str, Any], view: Any, context: Dict[str, Any]) -> Any:
        pass

    def node_create(self, tag: str, attrs: Dict[str, Any] = None, inner: List[Any] = None):
        """
        Crea un widget Textual da un tag DSL
        
        Implementa l'interfaccia di presentation.port
        Mapping DSL tag → Widget Textual
        """
        if attrs is None:
            attrs = {}
        if inner is None:
            inner = []
        
        content = "".join(str(i) for i in inner) if inner else ""
        node_id = attrs.get("id", str(uuid.uuid4()))
        
        # Mapping tag → Widget Textual
        if tag in ["h1", "h2", "h3", "h4", "h5", "h6", "p", "text", "span", "div"]:
            return Static(content, id=node_id)
        
        elif tag in ["input", "text", "email", "password", "search", "url"]:
            placeholder = attrs.get("placeholder", "")
            return Input(placeholder=placeholder, id=node_id)
        
        elif tag in ["button", "submit", "action"]:
            return Button(content, id=node_id)
        
        elif tag in ["row", "horizontal"]:
            return Horizontal(id=node_id)
        
        elif tag in ["column", "vertical"]:
            return Vertical(id=node_id)
        
        elif tag == "select":
            return Select([("Option", str(i)) for i in range(3)], id=node_id)
        
        elif tag == "textarea":
            return TextArea(id=node_id)
        
        else:
            # Widget generico di fallback
            return Static(f"[{tag.upper()}]", id=node_id)
    
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