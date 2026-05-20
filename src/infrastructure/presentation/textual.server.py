"""
textual.server.py — Adapter Textual TUI nativo per il Framework
Equivalente nativo di starlette.server.py

Integrazione diretta con il sistema di Dependency Injection del Framework.
Segue lo stesso pattern di Adapter(presentation.port) di Starlette.
"""

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


class PrimaApp(App):
    """Una semplice applicazione Textual."""
    
    # Definisce le scorciatoie da tastiera globali (visibili nel Footer)
    BINDINGS = [
        ("d", "toggle_dark", "Cambia Tema"),
        ("q", "quit", "Esci")
    ]

    def compose(self) -> ComposeResult:
        """Qui si definisce l'interfaccia utente."""
        yield Header()  # Barra superiore con il titolo
        yield Static("Benvenuto in Textual! Questa è una TUI moderna.", id="messaggio")
        yield Button("Cliccami!", id="mio_bottone", variant="success")
        yield Footer()  # Barra inferiore con le scorciatoie

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Gestore degli eventi: intercetta il click sul bottone."""
        if event.button.id == "mio_bottone":
            # Trova il widget con id 'messaggio' e ne aggiorna il testo
            self.query_one("#messaggio", Static).update("Hai premuto il bottone! 🎉")

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
        
        # Stato TUI
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.active_screens: Dict[str, 'TUIScreen'] = {}
        self.app = PrimaApp()
        
        self.initialize()
    
    def initialize(self):
        """Inizializzazione dell'adapter"""
        pass
    
    async def start(self):
        """
        Avvia l'applicazione TUI
        Equivalente di Starlette server.serve()
        
        Returns:
            Coroutine per esecuzione async
        """

        # Restituisci il coroutine di esecuzione (come fa Starlette)
        return self.app.run_async()
    
    def compose(self) -> ComposeResult:
        """Qui si definisce l'interfaccia utente."""
        yield Header()  # Barra superiore con il titolo
        yield Static("Benvenuto in Textual! Questa è una TUI moderna.", id="messaggio")
        yield Button("Cliccami!", id="mio_bottone", variant="success")
        yield Footer()  # Barra inferiore con le scorciatoie
    
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