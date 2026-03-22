"""
DAG Engine v7 - SESSION-AWARE + FRESHNESS FIXED
"""

import asyncio
import inspect
from typing import Any, Callable, List, Dict, Optional, Tuple
import networkx as nx
import time
from collections import ChainMap
from collections.abc import Mapping
import framework.service.scheme as scheme
import traceback

# -- RESULT SYSTEM --------------------------------------------------------------

_TAG = object()

def _make_result(success: bool, value=None, errors=None, t0=None):
    return {
        "success": success,
        "outputs": value if success else None,
        "errors":  errors if isinstance(errors, list) else ([str(errors)] if errors else []),
        "time":    (time.perf_counter() - t0) if t0 else 0.0,
        "_tag":    _TAG
    }

success   = lambda out, t0=None: _make_result(True,  out,  None, t0)
error     = lambda err, t0=None: _make_result(False, None, err,  t0)
is_result = lambda v: isinstance(v, dict) and v.get("_tag") is _TAG
value_of  = lambda v: v["outputs"] if is_result(v) else v

# -- DSL UTILITIES --------------------------------------------------------------

def step(fn: Callable, *args, **kwargs):
    return (fn, args, kwargs)

async def act(s):
    t0 = time.perf_counter()
    if not isinstance(s, tuple):
        return error("invalid step", t0)
    fn, args, kwargs = s
    try:
        r = await _call_if_coro(fn, *args, **kwargs)
        return r if is_result(r) else success(r, t0)
    except Exception as e:
        return error(e, t0)

# -- HELPERS --------------------------------------------------------------------

async def _call_if_coro(fn: Callable, *args, **kwargs):
    res = fn(*args, **kwargs)
    if inspect.isawaitable(res):
        return await res
    return res

def _set_path(data: Dict, path: str, value: Any):
    if not path: return
    parts = path.split('.')
    for part in parts[:-1]:
        data = data.setdefault(part, {})
    data[parts[-1]] = value

def _get_node_view(node_def, ctx, results, session_id=None):
    meta_deps = node_def.get("meta_deps", [])
    node_path = node_def.get("path") or node_def["name"]
    node_meta = {"path": node_path, "session_id": session_id} if session_id else {"path": node_path}
    
    # Scoped lookup
    parent_path = ".".join(node_path.split(".")[:-1])
    parent_scope = scheme.get(ctx, parent_path) if parent_path else {}
    if not isinstance(parent_scope, Mapping): parent_scope = {}

    view_parts = [node_meta, parent_scope, ctx]
    if meta_deps:
        view_parts.insert(1, {md: results[md] for md in meta_deps if md in results})
    
    return ChainMap(*view_parts)

def _parse_policy(policy) -> Tuple:
    if policy == "all":
        return ("all", None)
    if policy == "any":
        return ("any", None)
    if isinstance(policy, int) and policy >= 1:
        return ("quorum", policy)
    raise ValueError(f"deps_policy non valida: {policy!r}")

# -- NODE DEFINITION ------------------------------------------------------------

def node(name: str, fn: Callable, **kwargs) -> Dict[str, Any]:
    _parse_policy(kwargs.get("deps_policy", "all"))
    return {
        "name":        name,
        "fn":          fn,
        "deps":        kwargs.get("deps", []),
        "deps_policy":        kwargs.get("deps_policy", "all"),
        "ignore_failed_deps": kwargs.get("ignore_failed_deps", False),
        "meta_deps":          kwargs.get("meta", []),
        "schedule":           kwargs.get("schedule"),
        "duration":           kwargs.get("duration"),
        "on_start":           kwargs.get("on_start"),
        "on_success":         kwargs.get("on_success"),
        "on_error":           kwargs.get("on_error"),
        "when":               kwargs.get("when"),
        "timeout":            kwargs.get("timeout"),
        "retries":            kwargs.get("retries", 0),
        "retry_delay":        kwargs.get("retry_delay", 0),
        "path":               kwargs.get("path"),
    }

def pipeline(*args):
    """
    Crea una pipeline di step. 
    Supporta: 
      - pipeline(steps) -> factory che ritorna node_fn(ctx)
      - pipeline(data, steps) -> esecuzione immediata (utile in |>)
    """
    if len(args) == 2:
        data, steps = args
        return pipeline(steps)(data)
    
    steps = args[0]
    async def node_fn(*a, **ctx):
        # Determiniamo l'input iniziale: se a[0] non è un contesto, è il dato
        res = a[0] if (a and not isinstance(a[0], (dict, ChainMap))) else None
        runtime_ctx = ctx or (a[0] if (a and isinstance(a[0], (dict, ChainMap))) else {})
        
        for i, s in enumerate(steps):
            step_res = await act(step(s, res, **runtime_ctx))
            if not step_res["success"]:
                return step_res 
            res = step_res["outputs"]
        return res
    return node_fn

# -- CORE CHECKS ----------------------------------------------------------------

async def _check_deps(node_def, results, state, t0, ctx):
    deps = node_def.get("deps", [])
    if not deps:
        return True, False

    mode, quorum_n = _parse_policy(node_def.get("deps_policy", "all"))
    last_check = state["last_check"]
    ignore_failed = node_def.get("ignore_failed_deps", False)

    '''def _is_ok(d):
        has_res, exec_time = _get_dep_freshness(d, results)
        if not has_res or exec_time <= last_check: return False
        return ignore_failed or results[d]["success"]'''
    def _is_ok(d):
        # 1. nodo dinamico in results
        if d in results:
            res_d = results[d]
            if not (ignore_failed or res_d["success"]):
                return False
            if res_d.get("_static"):
                return True
            return res_d.get("_execution_time", 0.0) > last_check
        # 2. dato statico nel context (path annidato es. "health.cpu")
        return scheme.get(ctx, d) is not None

    fresh_ok = [d for d in deps if _is_ok(d)]
    
    existing = [d for d in deps if d in results]
    failed   = [d for d in existing if not results[d]["success"]]

    if mode == "all":
        if failed and not ignore_failed:
            results[node_def["name"]] = error(f"dep failed: {failed}", t0)
            return False, True
        return (len(fresh_ok) == len(deps)), False

    if mode == "any":
        if fresh_ok:
            return True, False
        if len(existing) == len(deps) and len(failed) == len(deps):
            return False, True
        return False, False

    if mode == "quorum":
        return (len(fresh_ok) >= quorum_n), False

    return False, False

# -- EXECUTION ------------------------------------------------------------------

async def _execute(node_def, ctx, results, view, t0):
    r = await _call_if_coro(node_def["fn"], view)
    result = r if is_result(r) else success(r, t0)
    result["_execution_time"] = time.perf_counter()
    
    node_name = node_def["name"]
    node_path = node_def.get("path") or node_name
    
    # Store in context (hierarchical)
    _set_path(ctx, node_path, result["outputs"])
    # Store in results (flat by internal path name for deps lookup)
    results[node_name] = result
    return result

# -- RUN NODE -------------------------------------------------------------------

async def _run_node(runner, session_id, node_name):
    file_name = runner.session_files[session_id]
    node_def  = runner.nodes_map[file_name][node_name]
    ctx       = runner.session_ctx[session_id]
    results   = runner.session_results[session_id]
    state     = runner.session_node_state[session_id][node_name]

    t0 = time.perf_counter()

    ok, fatal = await _check_deps(node_def, results, state, t0, ctx)

    if not ok:
        if fatal:
            state["done"].set()
        return

    state["last_check"] = t0
    view = _get_node_view(node_def, ctx, results, session_id)

    # 1. Conditional Execution (WHEN)
    when_cond = node_def.get("when")
    if when_cond:
        try:
            should_run = when_cond(view) if callable(when_cond) else bool(when_cond)
        except Exception as e:
            # Propaghiamo l'errore per debugging
            results[node_name] = error(f"WHEN condition error: {e}", t0)
            state["done"].set()
            return

        if not should_run:
            res = success(None, t0)
            res["_skipped"] = True
            res["_execution_time"] = time.perf_counter()
            results[node_name] = res
            
            # Notifica i successori anche se saltato
            file_name = runner.session_files[session_id]
            for succ in runner.graphs[file_name].successors(node_name):
                await runner.event_queue.put((session_id, succ))
                
            state["done"].set()
            return
    
    result = await _execute(node_def, ctx, results, view, t0)

    # successors dal grafo
    file_name = runner.session_files[session_id]
    for succ in runner.graphs[file_name].successors(node_name):
        await runner.event_queue.put((session_id, succ))

    # scheduling FIX
    if node_def.get("schedule"):
        async def resched():
            await asyncio.sleep(node_def["schedule"])
            await runner.event_queue.put((session_id, node_name))
        asyncio.create_task(resched())

    state["done"].set()

# -- DAGRUNNER ------------------------------------------------------------------

class DagRunner:

    def __init__(self, num_workers: int = 3):
        self.num_workers = num_workers
        self.nodes_map   = {}
        self.graphs      = {}
        self.files       = {}

        self.session_ctx        = {}
        self.session_results    = {}
        self.session_files      = {}
        self.session_node_state = {}

        self.event_queue = asyncio.Queue()
        self.tasks       = []
        self._running    = False
        self._stop_event = None

    async def _worker(self, wid):
        while self._running and not self._stop_event.is_set():
            try:
                session_id, node_name = await asyncio.wait_for(self.event_queue.get(), 0.2)
            except asyncio.TimeoutError:
                continue

            file_name = self.session_files.get(session_id)
            if not file_name or file_name not in self.nodes_map or node_name not in self.nodes_map[file_name]:
                self.event_queue.task_done()
                continue

            await _run_node(self, session_id, node_name)

            self.event_queue.task_done()

    async def start(self):
        self._running = True
        self._stop_event = asyncio.Event()
        for i in range(self.num_workers):
            self.tasks.append(asyncio.create_task(self._worker(i)))

    async def stop(self):
        self._running = False
        self._stop_event.set()
        for t in self.tasks:
            t.cancel()

    async def add_file(self, file_name: str, nodes: List[Dict]):
        G = nx.DiGraph()
        self.nodes_map[file_name] = {}

        node_names = {n["name"] for n in nodes}

        for n in nodes:
            name = n["name"]
            self.nodes_map[file_name][name] = n
            G.add_node(name)
            for d in n.get("deps", []):
                if d in node_names:
                    G.add_edge(d, name)

        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("DAG con cicli")

        self.graphs[file_name] = G
        self.files[file_name]  = [n["name"] for n in nodes]

        # Sync sessions that use this file
        for sid, fname in self.session_files.items():
            if fname == file_name:
                for n_name in self.files[file_name]:
                    if n_name not in self.session_node_state[sid]:
                        self.session_node_state[sid][n_name] = {
                            "last_check": -1.0,
                            "done": asyncio.Event()
                        }

    def create_session(self, session_id: str, file_name: str, context=None):
        self.session_ctx[session_id]     = dict(context or {})
        self.session_results[session_id] = {}
        self.session_files[session_id]   = file_name
        self.session_node_state[session_id] = {}

        for n in self.files[file_name]:
            self.session_node_state[session_id][n] = {
                "last_check": -1.0,
                "done": asyncio.Event()
            }

        for k, v in (context or {}).items():
            r = success(v)
            r["_execution_time"] = 0.0
            r["_static"] = True
            self.session_results[session_id][k] = r

        G = self.graphs[file_name]
        roots = [n for n in G.nodes if G.in_degree(n) == 0]

        for r in roots:
            self.event_queue.put_nowait((session_id, r))

    def push_event(self, session_id: str, node_name: str, value: Any):
        res = success(value)
        res["_execution_time"] = time.perf_counter()

        file_name = self.session_files.get(session_id)
        file_nodes = self.nodes_map.get(file_name, {})
        node_def = file_nodes.get(node_name, {})
        node_path = node_def.get("path") or node_name

        _set_path(self.session_ctx[session_id], node_path, value)
        self.session_results[session_id][node_name] = res

        self.event_queue.put_nowait((session_id, node_name))

    def trigger(self, session_id: str, node_name: str):
        self.event_queue.put_nowait((session_id, node_name))

    async def run_node(self, node_def: Dict, context: Dict):
        """Esegue un nodo immediatamente usando la logica dell'engine."""
        t0 = time.perf_counter()
        # Mocking basic view for immediate execution
        view = ChainMap(context, {"path": node_def.get("path") or node_def["name"]})
        res = await _call_if_coro(node_def["fn"], view)
        return res if is_result(res) else success(res, t0)

    async def invoke(self, fn: Callable, *args, **kwargs):
        """Esecuzione tracciata di una funzione tramite l'engine."""
        return await act(step(fn, *args, **kwargs))

    async def wait_node(self, session_id: str, node_name: str):
        if session_id not in self.session_node_state:
            raise KeyError(f"Session {session_id} does not exist")
        if node_name not in self.session_node_state[session_id]:
            raise KeyError(f"Node {node_name} does not exist in session")
        await self.session_node_state[session_id][node_name]["done"].wait()

# -- DAG EXTENSIONS -----------------------------------------------------------

def foreach(iterable, fn):
    """
    Esegue fn per ogni elemento dell'iterabile.
    Restituisce una lista di risultati.
    """
    async def _fn(view):
        items = view.get("items") or iterable
        results = []
        for item in items:
            new_view = ChainMap(view, {"item": item})
            res = await _call_if_coro(fn, new_view)
            results.append(res)
        return results
    return _fn

async def switch(data,cases):
    """
    Switch funzionale stile IF / ELIF / ELSE

    Esempio:
        switch({
            cond1: action1,
            cond2: action2,
            true:  default
        })

    - Le chiavi sono condizioni (callable o valori)
    - La prima condizione vera vince
    - 'true' è il default
    """
    
    default_fn = cases.get(True)

    for cond, fn in cases.items():

        # skip default, lo gestiamo alla fine
        if cond is True:
            continue

        if not callable(cond):
            continue
        else:
            check = cond(**data)

        if check is not True:
            continue

        try:
            if callable(fn):
                c, _ = await _call_if_coro(fn, data)
                return c
            else:
                return fn

        except Exception as e:
            errore_completo = traceback.format_exc()
            print(errore_completo,"e")
            raise RuntimeError(f"switch condition error: {e}")

    # default
    if default_fn:
        if callable(default_fn):
            a,_ = await _call_if_coro(default_fn, data)
            return a
        else:
            return default_fn

    return None