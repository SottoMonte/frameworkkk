
import contextvars
import uuid
from typing import Optional, Dict, Any, List

# Context var per propagare il transaction id nei flussi asincroni
_transaction_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('transaction_id', default=None)

def get_transaction_id() -> Optional[str]:
    """Restituisce il transaction id corrente dal contextvar, se presente."""
    return _transaction_id.get()

def set_transaction_id(tx: Optional[str]) -> contextvars.Token:
    """Imposta il transaction id corrente nel contextvar (pubblica API)."""
    if tx is None:
        return _transaction_id.set(None)
    
    if not isinstance(tx, str):
         tx = str(tx)
    
    return _transaction_id.set(tx)

# Context var per propagare i requirements dei servizi
_requirements: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar('requirements', default={})

def get_requirements() -> Dict[str, Any]:
    """Restituisce i requirements correnti dal contextvar."""
    return _requirements.get()

def _setup_transaction_context():
    """Gestisce l'inizializzazione del Transaction ID."""
    current_tx_id = get_transaction_id()
    tx_token = None
    if not current_tx_id:
        current_tx_id = str(uuid.uuid4())
        tx_token = set_transaction_id(current_tx_id)
    return current_tx_id, tx_token

class MockSpanContext:
    def __enter__(self): return self
    def __exit__(self, *args): pass

class MultiSpanContext:
    """Gestisce l'apertura di più span per una lista di provider di telemetria."""
    def __init__(self, telemetry_list, span_name, attributes=None):
        self.telemetry_list = telemetry_list or []
        self.span_name = span_name
        self.attributes = attributes
        self.spans = []

    def __enter__(self):
        for tel in self.telemetry_list:
            if hasattr(tel, 'start_span'):
                span = tel.start_span(self.span_name, attributes=self.attributes)
                if hasattr(span, '__enter__'):
                    span.__enter__()
                self.spans.append(span)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for span in reversed(self.spans):
            if hasattr(span, '__exit__'):
                span.__exit__(exc_type, exc_val, exc_tb)
