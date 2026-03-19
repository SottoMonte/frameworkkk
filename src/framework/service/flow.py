"""
DAG Engine v5 - REFACTOR ARCHITETTURALE: PARALLEL WORLDS (OPTIMIZED)
- ✅ Separazione netta: Mondo dei DATI (ctx) vs Mondo dei RISULTATI (results)
- ✅ Iniezione Dinamica: Ogni nodo sceglie cosa ricevere (puro o meta)
- ✅ Ottimizzazione 1: Riutilizzo della vista (ChainMap calcolato una sola volta)
- ✅ Ottimizzazione 2: Check dipendenze generativo (any/all)
- ✅ Ottimizzazione 3: Successori pre-risolti (no graph lookup a runtime)
- ✅ Ottimizzazione 4: Notifica Event-driven (no polling in wait_node/wait_file)
"""

import asyncio
from typing import Any, Callable, List, Dict, Optional
import networkx as nx
import time
from collections import ChainMap

# ── RESULT SYSTEM ──────────────────────────────────────────────────────────────

_TAG = object()

def _make_result(success: bool, value=None, errors=None, t0=None):
    return {
        "success": success,
        "outputs": value if success else None,
        "errors": errors if isinstance(errors, list) else ([str(errors)] if errors else []),
        "time": (time.perf_counter() - t0) if t0 else 0.0,
        "_tag": _TAG
    }

success = lambda out, t0=None: _make_result(True, out, None, t0)
error = lambda err, t0=None: _make_result(False, None, err, t0)
is_result = lambda v: isinstance(v, dict) and v.get("_tag") is _TAG
value_of = lambda v: v["outputs"] if is_result(v) else v

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

# ── HELPERS ────────────────────────────────────────────────────────────────────

async def _call_if_coro(fn: Callable, *args, **kwargs):
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return fn(*args, **kwargs)

def _get_node_view(node_def, ctx, results):
    """Costruisce una vista iniettando Dati Puri o Risultati in base alle richieste"""
    meta_deps = node_def.get("meta_deps", [])
    if not meta_deps:
        return ctx
    
    # Unione virtuale senza copia - Costo minimo
    meta_subset = {md: results[md] for md in meta_deps if md in results}
    return ChainMap(meta_subset, ctx)

# ── NODE DEFINITION ────────────────────────────────────────────────────────────

def node(name: str, fn: Callable, **kwargs) -> Dict[str, Any]:
    """Crea un nodo DAG con opzione per iniezione metadati"""
    return {
        "name": name,
        "fn": fn,
        "deps": kwargs.get("deps", []),
        "meta_deps": kwargs.get("meta", []),
        "schedule": kwargs.get("schedule"),
        "duration": kwargs.get("duration"),
        "on_start": kwargs.get("on_start"),
        "on_success": kwargs.get("on_success"),
        "on_error": kwargs.get("on_error"),
        "triggers": kwargs.get("triggers", []),
        "when": kwargs.get("when"),
        "timeout": kwargs.get("timeout"),
        "retries": kwargs.get("retries", 0),
        "retry_delay": kwargs.get("retry_delay", 0),
    }

# ── RUN HELPERS ────────────────────────────────────────────────────────────────

async def _check_deps(node_def, results, t0) -> bool:
    """Check dipendenze ottimizzato (generativo)"""
    deps = node_def.get("deps", [])
    if not deps: return True
    
    # Controllo istantaneo senza creare liste temporanee
    if any(d not in results for d in deps):
        return False
        
    failed = [d for d in deps if not results[d]["success"]]
    if failed:
        results[node_def["name"]] = error(f"dep failed: {', '.join(failed)}", t0)
        return False
        
    return True

async def _run_triggers(node_def, ctx, results, locks, nodes_map, queue):
    """Esegue in parallelo i triggers (Pull)"""
    triggers = node_def.get("triggers", [])
    if not triggers:
        return

    async def run_one(t_name):
        t_def = nodes_map.get(t_name)
        if t_def and t_name in locks:
            async with locks[t_name]:
                await _run_node(t_def, ctx, results, locks, nodes_map, queue)
    
    await asyncio.gather(*(run_one(tn) for tn in triggers))

async def _check_condition(node_def, view, results, t0) -> bool:
    """Valuta la condizione 'when' sulla vista riutilizzata"""
    when_fn = node_def.get("when")
    if when_fn:
        try:
            return await _call_if_coro(when_fn, **view)
        except Exception as e:
            results[node_def["name"]] = error(f"Condition 'when' failed: {e}", t0)
            return False
    return True

async def _run_hook(node_def, view, hook_name, extra_arg=None):
    """Esegue un hook del nodo sulla vista riutilizzata"""
    hook = node_def.get(hook_name)
    if not hook:
        return
    
    name = node_def["name"]
    if extra_arg is not None:
        await _call_if_coro(hook, name, extra_arg, view)
    else:
        await _call_if_coro(hook, name, view)

async def _execute_with_retry(node_def, ctx, results, view, t0):
    """Tentativi di esecuzione atomica"""
    retries = node_def.get("retries", 0)
    delay = node_def.get("retry_delay", 0)
    
    for attempt in range(retries + 1):
        try:
            return await _call_node_fn(node_def, ctx, results, view, t0)
        except Exception as e:
            if attempt < retries:
                if delay > 0: await asyncio.sleep(delay)
                continue
            res = error(e, t0)
            ctx[node_def["name"]] = None
            results[node_def["name"]] = res
            return res

async def _call_node_fn(node_def, ctx, results, view, t0):
    """Esecuzione funzione nodo sulla vista riutilizzata"""
    name = node_def["name"]
    timeout = node_def.get("timeout")
    
    if timeout:
        r = await asyncio.wait_for(_call_if_coro(node_def["fn"], view), timeout=timeout)
    else:
        r = await _call_if_coro(node_def["fn"], view)
        
    result = r if is_result(r) else success(r, t0)
    ctx[name] = result["outputs"]
    results[name] = result
    return result

async def _handle_post_run(node_def, result, ctx, results, queue):
    """Post-esecuzione ottimizzata (no graph search)"""
    # 1. Trigger successori (Push)
    await _trigger_successors(node_def, result, queue)
    # 2. Scheduling
    await _handle_scheduling(node_def, ctx, results, queue)

async def _trigger_successors(node_def, result, queue):
    """Notifica i successori usando la lista pre-risolta"""
    if result["success"] and queue:
        for succ in node_def.get("_successors", []):
            try:
                queue.put_nowait(succ)
            except asyncio.QueueFull:
                await queue.put(succ)

async def _handle_scheduling(node_def, ctx, results, queue):
    """Gestione timer interni"""
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
                    try: queue.put_nowait(name)
                    except asyncio.QueueFull: await queue.put(name)
            asyncio.create_task(reschedule_task())
        elif "_schedule_start" in ctx and name in ctx["_schedule_start"]:
            del ctx["_schedule_start"][name]

# ── CORE EXECUTION ─────────────────────────────────────────────────────────────

async def _run_node(node_def, ctx, results, locks, nodes_map, queue=None):
    """Esegue un nodo con ottimizzazioni attive"""
    t0 = time.perf_counter()
    
    # 1. Dipendenze
    if not await _check_deps(node_def, results, t0):
        return
    await _run_triggers(node_def, ctx, results, locks, nodes_map, queue)
    
    # Ottimizzazione 1: Vista calcolata una sola volta
    view = _get_node_view(node_def, ctx, results)
    
    # 2. Condizione
    if not await _check_condition(node_def, view, results, t0):
        await _handle_scheduling(node_def, ctx, results, queue)
        return

    # 3. Esecuzione
    await _run_hook(node_def, view, "on_start")
    result = await _execute_with_retry(node_def, ctx, results, view, t0)
    
    if result["success"]:
        await _run_hook(node_def, view, "on_success", result)
    else:
        err_msg = ", ".join(result["errors"])
        await _run_hook(node_def, view, "on_error", err_msg)

    # 4. Successori e Scheduling
    await _handle_post_run(node_def, result, ctx, results, queue)
    
    # Ottimizzazione 4: Notifica completamento (Event)
    event = node_def.get("_done_event")
    if event:
        event.set()

# ── DAGRUNNER ──────────────────────────────────────────────────────────────────

class DagRunner:
    """DAG Runner ad alte prestazioni - Parallel Worlds Architecture"""
    
    def __init__(self, num_workers: int = 3):
        self.num_workers = num_workers
        self.nodes_map = {}
        self.context_by_file = {}
        self.results_by_file = {}
        self.files = {}
        self.graphs = {}
        
        self.q = None
        self.locks = {}
        self.tasks = []
        self._running = False
        self._stop_event = None
    
    def _find_file_for_node(self, node_name: str) -> Optional[str]:
        for file_name, node_names in self.files.items():
            if node_name in node_names:
                return file_name
        return None

    async def _worker(self, worker_id: int):
        try:
            while self._running and not self._stop_event.is_set():
                try:
                    node_name = await asyncio.wait_for(self.q.get(), timeout=0.2)
                except asyncio.TimeoutError: continue
                except asyncio.CancelledError: break
                
                if node_name is None:
                    self.q.task_done()
                    break
                
                try:
                    name = node_name
                    if name not in self.nodes_map:
                        self.q.task_done()
                        continue
                    
                    file_name = self._find_file_for_node(name)
                    if not file_name:
                        self.q.task_done()
                        continue
                    
                    async with self.locks[name]:
                        node_def = self.nodes_map[name]
                        ctx = self.context_by_file[file_name]
                        results = self.results_by_file[file_name]
                        
                        await _run_node(node_def, ctx, results, self.locks, self.nodes_map, self.q)
                finally:
                    self.q.task_done()
        except asyncio.CancelledError: pass
    
    async def start(self):
        if self._running: return
        self._running = True
        self._stop_event = asyncio.Event()
        self.q = asyncio.Queue()
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker(i))
            self.tasks.append(task)
    
    async def stop(self):
        if not self._running: return
        self._running = False
        self._stop_event.set()
        try: await asyncio.wait_for(self.q.join(), timeout=2.0)
        except asyncio.TimeoutError: pass
        for task in self.tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
    
    async def add_file(self, file_name: str, nodes: List[Dict], context: dict = None):
        G = nx.DiGraph()
        for n in nodes:
            name = n["name"]
            self.nodes_map[name] = n
            self.locks[name] = asyncio.Lock()
            # Ottimizzazione 4: Registro un Event per ogni nodo
            n["_done_event"] = asyncio.Event()
            G.add_node(name)
            for d in n.get("deps", []):
                G.add_edge(d, name)
        
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError(f"File {file_name}: DAG contiene cicli!")
        
        # Ottimizzazione 3: Pre-risoluzione dei successori
        for n_name in G.nodes:
            if n_name in self.nodes_map:
                self.nodes_map[n_name]["_successors"] = list(G.successors(n_name))
        
        self.files[file_name] = [n["name"] for n in nodes]
        self.context_by_file[file_name] = dict(context or {})
        
        # Setup Risultati iniziali
        res_dict = {}
        for k, v in (context or {}).items():
            res_dict[k] = success(v)
            res_dict[k]["time"] = 0.0
        self.results_by_file[file_name] = res_dict
        self.graphs[file_name] = G
        
        if self._running and self.q:
            for gen in nx.topological_generations(G):
                for name in gen:
                    if name in self.files[file_name]:
                        try: self.q.put_nowait(name)
                        except asyncio.QueueFull: await self.q.put(name)

    def get_file_context(self, file_name: str) -> dict:
        ctx = dict(self.context_by_file.get(file_name, {}))
        return {k: v for k, v in ctx.items() if not k.startswith("_")}
    
    def get_file_results(self, file_name: str) -> dict:
        return dict(self.results_by_file.get(file_name, {}))
    
    def file_status(self, file_name: str) -> dict:
        nodes = self.files.get(file_name, [])
        results = self.results_by_file.get(file_name, {})
        executed = sum(1 for n in nodes if n in results)
        successful = sum(1 for n in nodes if n in results and results[n]["success"])
        return {
            "total": len(nodes), "executed": executed, "successful": successful,
            "pending": len(nodes) - executed, "failed": executed - successful,
        }
    
    async def wait_file(self, file_name: str):
        """Attesa Event-driven per file"""
        nodes = self.files.get(file_name, [])
        if not nodes: return
        # Aspettiamo che tutti i nodi abbiano scatenato il loro evento
        await asyncio.gather(*(self.nodes_map[n]["_done_event"].wait() for n in nodes if n in self.nodes_map))

    async def wait_node(self, file_name: str, node_name: str):
        """Attesa Event-driven per nodo"""
        if node_name in self.nodes_map:
            await self.nodes_map[node_name]["_done_event"].wait()

    def get_all_contexts(self) -> dict:
        return {file: self.get_file_context(file) for file in self.files.keys()}