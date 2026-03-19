"""
DAG Engine v5 - REFACTOR RADICALE
- ✅ Un UNICO dizionario (context)
- ✅ Input iniziale + Output risultati = STESSO DICT
- ✅ No env/ctx separation - è tutto context!
- ✅ Pulito e logico
- ✅ Schedule/Duration support
"""

import asyncio
from typing import Any, Callable, List, Dict, Optional
import networkx as nx
import time

# ── RESULT SYSTEM ──────────────────────────────────────────────────────────────

_TAG = object()

def _make_result(success: bool, value=None, errors=None, t0=None):
    return {
        "success": success,
        "outputs": value if success else None,
        "errors": errors if isinstance(errors, list) else ([str(errors)] if errors else []),
        "time": (time.perf_counter() - t0) if t0 else None,
        "_tag": _TAG
    }

success = lambda out, t0=None: _make_result(True, out, None, t0)
error = lambda err, t0=None: _make_result(False, None, err, t0)
output = lambda v: v["outputs"] if is_result(v) else v
is_result = lambda v: isinstance(v, dict) and v.get("_tag") is _TAG
value_of = lambda v: v["outputs"] if is_result(v) else v

# ── HELPERS ────────────────────────────────────────────────────────────────────

async def _call_if_coro(fn: Callable, *args, **kwargs):
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return fn(*args, **kwargs)

# ── NODE DEFINITION ────────────────────────────────────────────────────────────

def node(name: str, fn: Callable, **kwargs) -> Dict[str, Any]:
    """Crea un nodo DAG"""
    return {
        "name": name,
        "fn": fn,
        "deps": kwargs.get("deps", []),
        "schedule": kwargs.get("schedule"),
        "duration": kwargs.get("duration"),
        "on_start": kwargs.get("on_start"),
        "on_success": kwargs.get("on_success"),
        "on_error": kwargs.get("on_error"),
        "triggers": kwargs.get("triggers", []),
        "when": kwargs.get("when"),       # Aggiunto 'when' (condizione booleana)
        "timeout": kwargs.get("timeout"), # Aggiunto 'timeout' (secondi)
        "retries": kwargs.get("retries", 0),         # Numero di tentativi in caso di errore
        "retry_delay": kwargs.get("retry_delay", 0), # Ritardo tra i tentativi (secondi)
    }

# ── RUN HELPERS ────────────────────────────────────────────────────────────────

def _get_clean_ctx(ctx: dict) -> dict:
    """Restituisce una vista del contesto con i valori dei risultati scompattati (unwrapped)"""
    return {k: value_of(v) for k, v in ctx.items() if not k.startswith("_")}

async def _check_deps(node_def, ctx, t0) -> bool:
    """Controlla se le dipendenze sono soddisfatte"""
    name = node_def["name"]
    deps = node_def.get("deps", [])
    
    # 1. Dipendenze mancanti?
    missing = [d for d in deps if not is_result(ctx.get(d))]
    if missing:
        return False
        
    # 2. Dipendenze fallite?
    failed = [d for d in deps if not ctx[d]["success"]]
    if failed:
        ctx[name] = error(f"dep failed: {', '.join(failed)}", t0)
        return False
        
    return True

async def _run_triggers(node_def, ctx, locks, nodes_map, queue, get_graph):
    """Esegue in parallelo i triggers (Pull)"""
    triggers = node_def.get("triggers", [])
    if not triggers:
        return

    async def run_one(t_name):
        t_def = nodes_map.get(t_name)
        if t_def and t_name in locks:
            async with locks[t_name]:
                await _run_node(t_def, ctx, locks, nodes_map, queue, get_graph)
    
    await asyncio.gather(*(run_one(tn) for tn in triggers))

async def _check_condition(node_def, ctx, t0) -> bool:
    """Valuta la condizione 'when' fornendo un contesto pulito"""
    when_fn = node_def.get("when")
    if when_fn:
        try:
            # Scompattiamo i risultati per permettere accesso diretto @var
            clean_ctx = _get_clean_ctx(ctx)
            print(clean_ctx['level'])
            return await _call_if_coro(when_fn, **clean_ctx)
        except Exception as e:
            ctx[node_def["name"]] = error(f"condition 'when' failed: {e}", t0)
            return False
    return True

async def _run_hook(node_def, ctx, hook_name, extra_arg=None):
    """Esegue un hook del nodo passando il contesto pulito"""
    hook = node_def.get(hook_name)
    if not hook:
        return
    
    name = node_def["name"]
    clean_ctx = _get_clean_ctx(ctx)
    if extra_arg is not None:
        await _call_if_coro(hook, name, extra_arg, clean_ctx)
    else:
        await _call_if_coro(hook, name, clean_ctx)

async def _execute_with_retry(node_def, ctx, t0):
    """Gestisce puramente il loop di retry e il delay tra tentativi"""
    retries = node_def.get("retries", 0)
    delay = node_def.get("retry_delay", 0)
    
    for attempt in range(retries + 1):
        try:
            return await _call_node_fn(node_def, ctx, t0)
        except Exception as e:
            if attempt < retries:
                if delay > 0:
                    await asyncio.sleep(delay)
                continue
            # Se tutti i tentativi falliscono: registra e restituisci l'errore
            res = error(e, t0)
            ctx[node_def["name"]] = res
            return res

async def _call_node_fn(node_def, ctx, t0):
    """Esegue la funzione del nodo passando il contesto pulito"""
    name = node_def["name"]
    timeout = node_def.get("timeout")
    clean_ctx = _get_clean_ctx(ctx)
    
    if timeout:
        r = await asyncio.wait_for(_call_if_coro(node_def["fn"], clean_ctx), timeout=timeout)
    else:
        r = await _call_if_coro(node_def["fn"], clean_ctx)
        
    result = r if is_result(r) else success(r, t0)
    ctx[name] = result
    return result

async def _handle_post_run(node_def, result, ctx, queue, get_graph):
    """Orchestra le attività post-esecuzione"""
    # 1. Trigger successori (Push)
    await _trigger_successors(node_def, result, queue, get_graph)
    # 2. Scheduling
    await _handle_scheduling(node_def, ctx, queue)

async def _trigger_successors(node_def, result, queue, get_graph):
    """Notifica e accoda i successori reattivi"""
    name = node_def["name"]
    graph = get_graph(name) if get_graph else None
    if result["success"] and graph and queue:
        if name in graph:
            for succ in graph.successors(name):
                try:
                    queue.put_nowait(succ)
                except asyncio.QueueFull:
                    await queue.put(succ)

async def _handle_scheduling(node_def, ctx, queue):
    """Gestisce il reschedule temporizzato se configurato"""
    name = node_def["name"]
    schedule = node_def.get("schedule")
    duration = node_def.get("duration")
    
    if schedule and queue:
        should_reschedule = True
        
        if duration:
            if "_schedule_start" not in ctx:
                ctx["_schedule_start"] = {}
            if name not in ctx["_schedule_start"]:
                ctx["_schedule_start"][name] = time.perf_counter()
            
            elapsed = time.perf_counter() - ctx["_schedule_start"][name]
            if elapsed >= duration:
                should_reschedule = False
        
        if should_reschedule:
            async def reschedule_task():
                await asyncio.sleep(schedule)
                if queue:
                    try:
                        queue.put_nowait(name)
                    except asyncio.QueueFull:
                        await queue.put(name)
            
            asyncio.create_task(reschedule_task())
        elif "_schedule_start" in ctx and name in ctx["_schedule_start"]:
            del ctx["_schedule_start"][name]

# ── CORE EXECUTION ─────────────────────────────────────────────────────────────

async def _run_node(node_def, ctx, locks, nodes_map, queue=None, get_graph: Callable = None):
    """Esegue un nodo del DAG orchestrando i vari passaggi atomici"""
    t0 = time.perf_counter()
    
    # 1. Controlli Preliminari
    if not await _check_deps(node_def, ctx, t0):
        return
    await _run_triggers(node_def, ctx, locks, nodes_map, queue, get_graph)

    # 2. Controllo Condizione (Se falsa, manteniamo comunque lo scheduling)
    if not await _check_condition(node_def, ctx, t0):
        await _handle_scheduling(node_def, ctx, queue)
        return

    # 2. Lifecycle del Nodo (Hooks + Esecuzione Atomica)
    await _run_hook(node_def, ctx, "on_start")
    
    result = await _execute_with_retry(node_def, ctx, t0)
    
    if result["success"]:
        await _run_hook(node_def, ctx, "on_success", result)
    else:
        err_msg = ", ".join(result["errors"])
        await _run_hook(node_def, ctx, "on_error", err_msg)

    # 3. Gestione Post-Esecuzione (Successori e Scheduling)
    await _handle_post_run(node_def, result, ctx, queue, get_graph)

    

# ── DAGRUNNER ──────────────────────────────────────────────────────────────────

class DagRunner:
    """
    DAG Runner - Context UNICO
    
    - Un UNICO dizionario per file
    - Input + Output = STESSO DICT
    - Semplice e logico
    - Support per schedule/duration
    """
    
    def __init__(self, num_workers: int = 3):
        self.num_workers = num_workers
        
        # State
        self.nodes_map = {}        # Tutti i nodi
        self.context_by_file = {}  # UNICO context per file (input + output)
        self.files = {}            # Mapping file -> nodes
        self.graphs = {}           # Mapping file -> graph
        
        # Async
        self.q = None
        self.locks = {}
        self.tasks = []
        self._running = False
        self._stop_event = None
    
    def _find_file_for_node(self, node_name: str) -> Optional[str]:
        """Trova quale file contiene questo nodo"""
        for file_name, node_names in self.files.items():
            if node_name in node_names:
                return file_name
        return None
    
    def _get_graph_for_node(self, node_name: str) -> Optional[nx.DiGraph]:
        """Trova il grafo che contiene questo nodo"""
        file_name = self._find_file_for_node(node_name)
        return self.graphs.get(file_name) if file_name else None

    async def _worker(self, worker_id: int):
        """Worker asincrono"""
        try:
            while self._running and not self._stop_event.is_set():
                try:
                    node_name = await asyncio.wait_for(self.q.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                
                if node_name is None:
                    self.q.task_done()
                    break
                
                try:
                    if node_name not in self.nodes_map:
                        self.q.task_done()
                        continue
                    
                    file_name = self._find_file_for_node(node_name)
                    if not file_name:
                        self.q.task_done()
                        continue
                    
                    async with self.locks[node_name]:
                        node_def = self.nodes_map[node_name]
                        ctx = self.context_by_file[file_name]
                        
                        # Esegui nodo con context UNIFICATO, queue e provider di grafi per scheduling/reattività
                        await _run_node(node_def, ctx, self.locks, self.nodes_map, self.q, self._get_graph_for_node)
                
                finally:
                    self.q.task_done()
        
        except asyncio.CancelledError:
            pass
    
    async def start(self):
        """Avvia runner"""
        if self._running:
            return
        
        self._running = True
        self._stop_event = asyncio.Event()
        self.q = asyncio.Queue()
        
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker(i))
            self.tasks.append(task)
    
    async def stop(self):
        """Ferma runner"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        try:
            await asyncio.wait_for(self.q.join(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
    
    # ── FILE MANAGEMENT ────────────────────────────────────────────────────────
    
    async def add_file(self, file_name: str, nodes: List[Dict], context: dict = None):
        """
        Aggiungi file con nodi
        
        Args:
            file_name: Nome file/key
            nodes: Lista nodi da eseguire
            context: Context iniziale (input) per questo file
                     Verrà aggiornato col risultato dei nodi
        """
        # Valida DAG
        G = nx.DiGraph()
        for n in nodes:
            self.nodes_map[n["name"]] = n
            self.locks[n["name"]] = asyncio.Lock()
            G.add_node(n["name"])
            for d in n.get("deps", []):
                G.add_edge(d, n["name"])
        
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError(f"File {file_name}: DAG contiene cicli!")
        
        # Setup file context UNICO
        self.files[file_name] = [n["name"] for n in nodes]
        self.context_by_file[file_name] = dict(context or {})
        self.graphs[file_name] = G
        
        # Accodamento topologico iniziale
        if self._running and self.q:
            # Notiamo che ora _run_node salterà i nodi con dipendenze mancanti
            # Quindi accodare tutto è sicuro, ma per efficienza accodiamo 
            # in ordine topologico.
            for gen in nx.topological_generations(G):
                for name in gen:
                    if name in self.files[file_name]:
                        try:
                            self.q.put_nowait(name)
                        except asyncio.QueueFull:
                            await self.q.put(name)
    
    # ── QUERY RESULTS ──────────────────────────────────────────────────────────
    
    def get_file_context(self, file_name: str) -> dict:
        """
        Ottieni context completo di un file
        
        Contiene:
        - Input iniziale
        - Output di tutti i nodi eseguiti
        """
        ctx = dict(self.context_by_file.get(file_name, {}))
        # Rimuovi metadati interni
        ctx.pop("_schedule_start", None)
        return ctx
    
    def get_all_contexts(self) -> dict:
        """Ottieni tutti i context per file"""
        return {file: self.get_file_context(file) 
                for file in self.files.keys()}
    
    def file_status(self, file_name: str) -> dict:
        """Status di un file"""
        nodes = self.files.get(file_name, [])
        ctx = self.context_by_file.get(file_name, {})
        
        executed = sum(1 for n in nodes if is_result(ctx.get(n)))
        successful = sum(1 for n in nodes if is_result(ctx.get(n)) and ctx[n]["success"])
        
        return {
            "total": len(nodes),
            "executed": executed,
            "successful": successful,
            "pending": len(nodes) - executed,
            "failed": executed - successful,
        }
    
    # ── WAITING (NO TIMEOUT) ───────────────────────────────────────────────────
    
    async def wait_file(self, file_name: str):
        """Aspetta che TUTTI i nodi di un file si eseguano"""
        nodes = self.files.get(file_name, [])
        if not nodes:
            return
        
        while True:
            ctx = self.context_by_file.get(file_name, {})
            all_done = all(is_result(ctx.get(n)) for n in nodes)
            if all_done:
                return
            await asyncio.sleep(0.01)
    
    async def wait_node(self, file_name: str, node_name: str):
        """Aspetta che un nodo specifico si esegua"""
        while True:
            ctx = self.context_by_file.get(file_name, {})
            if is_result(ctx.get(node_name)):
                return
            await asyncio.sleep(0.01)
    
    # ── INFO ───────────────────────────────────────────────────────────────────
    
    def is_running(self) -> bool:
        return self._running
    
    def get_files(self) -> List[str]:
        return list(self.files.keys())
    
    def get_nodes_count(self) -> int:
        return len(self.nodes_map)


# ── DSL UTILITIES ──────────────────────────────────────────────────────────────

def step(fn: Callable, *args, **kwargs):
    """Crea uno step DSL"""
    return (fn, args, kwargs)

async def act(s):
    """Esegui uno step DSL"""
    t0 = time.perf_counter()
    if not isinstance(s, tuple):
        return error("invalid step", t0)
    fn, args, kwargs = s
    try:
        r = await _call_if_coro(fn, *args, **kwargs)
        return r if is_result(r) else success(r, t0)
    except Exception as e:
        return error(e, t0)