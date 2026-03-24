import json
import traceback
import sys
import os
import platform
import socket
import psutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import time
import contextvars


# =====================================================================
# --- Utilities di Base ---
# =====================================================================

class DiagnosticEncoder(json.JSONEncoder):
    """JSONEncoder per serializzare oggetti complessi nei report diagnostici."""
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def truncate_value(value: Any, max_str_len: int = 256, max_list_len: int = 20) -> Any:
    """Tronca stringhe e collezioni troppo grandi."""
    if isinstance(value, str):
        if len(value) > max_str_len:
            return f"{value[:max_str_len]}... [TRONCATA, L={len(value)}]"
        return value

    elif isinstance(value, (list, tuple, set)):
        if len(value) > max_list_len:
            truncated = list(value)[:max_list_len]
            return f"{truncated} ... [TRONCATA, N={len(value)}]"
        return list(value)
        
    elif isinstance(value, dict):
        return {k: truncate_value(v, max_str_len, max_list_len) for k, v in value.items()}

    return value


# =====================================================================
# --- Analisi Exception ---
# =====================================================================

def get_system_info() -> Dict[str, Any]:
    """Raccoglie informazioni di sistema."""
    mem = psutil.virtual_memory()
    return {
        "hostname": socket.gethostname(),
        "process_id": os.getpid(),
        "cpu_cores": psutil.cpu_count(),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_available_gb": round(mem.available / (1024**3), 2),
        "os_name": platform.platform(),
        "python_version": platform.python_version(),
    }


def analyze_traceback(tb) -> List[Dict[str, Any]]:
    """Estrae informazioni strutturate dal traceback."""
    frames = []
    current_tb = tb
    
    while current_tb is not None:
        frame = current_tb.tb_frame
        filename = frame.f_code.co_filename
        
        # Salta librerie di sistema
        if "/usr/" in filename or "/lib/python" in filename:
            current_tb = current_tb.tb_next
            continue

        # Estrai variabili locali (escluse quelle interne)
        local_vars = {
            k: truncate_value(v)
            for k, v in frame.f_locals.items() 
            if not k.startswith('_')
        }
        
        # Recupera la riga di codice
        try:
            frame_summary = traceback.FrameSummary(
                filename, 
                current_tb.tb_lineno, 
                frame.f_code.co_name, 
                lookup_line=True
            )
            code_line = frame_summary.line.strip() if frame_summary.line else "N/A"
        except Exception:
            code_line = "N/A"
        
        frames.append({
            "filename": filename,
            "line_number": current_tb.tb_lineno,
            "function": frame.f_code.co_name,
            "code_line": code_line,
            "local_variables": local_vars
        })
        
        current_tb = current_tb.tb_next
    
    return frames


def create_diagnostic_report(exc_info: tuple = None) -> Dict[str, Any]:
    """
    Genera un report diagnostico dettagliato per un'eccezione.
    
    Args:
        exc_info: Tuple (type, value, traceback) dell'eccezione. 
                  Se None, usa sys.exc_info()
    
    Returns:
        Dizionario con il report completo
    """
    if exc_info:
        exc_type, exc_value, exc_traceback = exc_info
    else:
        exc_type, exc_value, exc_traceback = sys.exc_info()
    
    if exc_type is None:
        return {"status": "Nessuna eccezione attiva"}
        
    # Analizza il traceback
    frames = analyze_traceback(exc_traceback)
    
    # Frame finale (dove è avvenuto l'errore)
    final_frame = frames[-1] if frames else {}
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "system_info": get_system_info(),
        "exception": {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "location": {
                "filename": final_frame.get("filename", "N/A"),
                "line_number": final_frame.get("line_number", 0),
                "function": final_frame.get("function", "N/A"),
                "code_line": final_frame.get("code_line", "N/A"),
            },
            "final_frame_variables": final_frame.get("local_variables", {}),
        },
        "traceback_frames": frames,
        "traceback_formatted": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    }
    
    return report


def save_diagnostic_report(report: Dict[str, Any], output_dir: str = ".diagnostics") -> str:
    """Salva il report diagnostico su file."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"diagnostic_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(report, f, cls=DiagnosticEncoder, indent=2)
    
    return filepath


# =====================================================================
# --- Logging Diagnostico ---
# =====================================================================

# Colori ANSI
COLOR_RESET = "\033[0m"
COLORS = {
    "DEBUG": "\033[37m",
    "INFO": "\033[96m",
    "WARNING": "\033[93m",
    "ERROR": "\033[91m",
    "CRITICAL": "\033[95m",
}

_log_indent: contextvars.ContextVar[int] = contextvars.ContextVar("log_indent", default=0)


@contextmanager
def timed_block(title: str, level: str = "INFO"):
    """Context manager per misurare e loggare la durata di un blocco."""
    indent = _log_indent.get()
    token = _log_indent.set(indent + 1)
    
    log(level, f"{title} - Starting...")
    start_time = time.perf_counter()
    
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        _log_indent.reset(token)
        log(level, f"{title} - Completed in {duration:.3f}s")


def log(level: str, message: str, **metadata):
    """
    Logger diagnostico con supporto per metadata ed eccezioni.
    
    Args:
        level: Livello di log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Messaggio da loggare
        **metadata: Dati aggiuntivi (es: exception, context, etc.)
    """
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    color = COLORS.get(level.upper(), "")
    
    # Indentazione per blocchi annidati
    indent = _log_indent.get()
    indent_str = "  " * indent
    
    # Log principale
    print(f"{color}[{timestamp}] [{level:8}] {indent_str}{message}{COLOR_RESET}")
    
    # Gestione eccezioni
    if "exception" in metadata:
        exc = metadata.pop("exception")
        if isinstance(exc, Exception):
            exc_info = (type(exc), exc, exc.__traceback__)
            report = create_diagnostic_report(exc_info)
            
            # Stampa traceback formattato
            print(f"{color}{indent_str}  Traceback:{COLOR_RESET}")
            for line in report["traceback_formatted"].splitlines():
                print(f"{color}{indent_str}    {line}{COLOR_RESET}")
            
            # Salva report se ERROR o CRITICAL
            if level.upper() in ("ERROR", "CRITICAL"):
                filepath = save_diagnostic_report(report)
                print(f"{color}{indent_str}  📝 Report salvato: {filepath}{COLOR_RESET}")
    
    # Stampa metadata aggiuntivi
    for key, value in metadata.items():
        value_str = truncate_value(value, max_str_len=200)
        print(f"{color}{indent_str}  {key}: {value_str}{COLOR_RESET}")