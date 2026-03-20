"""
DAG Engine v7 - SESSION-AWARE + FRESHNESS FIXED
"""

import asyncio
from typing import Any, Callable, List, Dict, Optional, Tuple
import networkx as nx
import time
from collections import ChainMap

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
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return fn(*args, **kwargs)

def _get_node_view(node_def, ctx, results, session_id=None):
    meta_deps = node_def.get("meta_deps", [])
    if session_id:
        ctx["session_id"] = session_id
    if not meta_deps:
        return ctx
    meta_subset = {md: results[md] for md in meta_deps if md in results}
    return ChainMap(meta_subset, ctx)

def _parse_policy(policy) -> Tuple:
    if policy == "all":
        return ("all", None)
    if policy == "any":
        return ("any", None)
    if isinstance(policy, int) and policy >= 1:
        return ("quorum", policy)
    raise ValueError(f"deps_policy non valida: {policy!r}")

# -- FRESHNESS LOGIC ------------------------------------------------------------

def _get_dep_freshness(dep_name: str, results: dict) -> Tuple[bool, float]:
    if dep_name not in results:
        return False, 0.0
    res = results[dep_name]
    return True, res.get("_execution_time", 0.0)

def _is_dep_satisfied(dep_name: str, results: dict, node_last_check: float) -> bool:
    has_result, exec_time = _get_dep_freshness(dep_name, results)
    if not has_result:
        return False
    res = results[dep_name]
    return res.get("success", False) and (exec_time > node_last_check)

# -- NODE DEFINITION ------------------------------------------------------------

def node(name: str, fn: Callable, **kwargs) -> Dict[str, Any]:
    _parse_policy(kwargs.get("deps_policy", "all"))
    return {
        "name":        name,
        "fn":          fn,
        "deps":        kwargs.get("deps", []),
        "deps_policy": kwargs.get("deps_policy", "all"),
        "meta_deps":   kwargs.get("meta", []),
        "schedule":    kwargs.get("schedule"),
        "duration":    kwargs.get("duration"),
        "on_start":    kwargs.get("on_start"),
        "on_success":  kwargs.get("on_success"),
        "on_error":    kwargs.get("on_error"),
        "when":        kwargs.get("when"),
        "timeout":     kwargs.get("timeout"),
        "retries":     kwargs.get("retries", 0),
        "retry_delay": kwargs.get("retry_delay", 0),
    }

# -- CORE CHECKS ----------------------------------------------------------------

async def _check_deps(node_def, results, state, t0):
    deps = node_def.get("deps", [])
    if not deps:
        return True, False

    mode, quorum_n = _parse_policy(node_def.get("deps_policy", "all"))
    last_check = state["last_check"]

    fresh_ok = [d for d in deps if _is_dep_satisfied(d, results, last_check)]
    existing = [d for d in deps if d in results]
    failed   = [d for d in existing if not results[d]["success"]]

    if mode == "all":
        if failed:
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
    ctx[node_def["name"]] = result["outputs"]
    results[node_def["name"]] = result
    return result

# -- RUN NODE -------------------------------------------------------------------

async def _run_node(runner, session_id, node_name):
    node_def = runner.nodes_map[node_name]
    ctx      = runner.session_ctx[session_id]
    results  = runner.session_results[session_id]
    state    = runner.session_node_state[session_id][node_name]

    t0 = time.perf_counter()

    ok, fatal = await _check_deps(node_def, results, state, t0)
    state["last_check"] = t0

    if not ok:
        if fatal:
            state["done"].set()
        return

    view = _get_node_view(node_def, ctx, results, session_id)

    result = await _execute(node_def, ctx, results, view, t0)

    # successors dal grafo
    file_name = runner.session_files[session_id]
    G = runner.graphs[file_name]

    for succ in G.successors(node_name):
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

            if node_name not in self.nodes_map:
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

        for n in nodes:
            name = n["name"]
            self.nodes_map[name] = n
            G.add_node(name)
            for d in n.get("deps", []):
                G.add_edge(d, name)

        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("DAG con cicli")

        self.graphs[file_name] = G
        self.files[file_name]  = [n["name"] for n in nodes]

    def create_session(self, session_id: str, file_name: str, context=None):
        self.session_ctx[session_id]     = dict(context or {})
        self.session_results[session_id] = {}
        self.session_files[session_id]   = file_name
        self.session_node_state[session_id] = {}

        for n in self.files[file_name]:
            self.session_node_state[session_id][n] = {
                "last_check": 0.0,
                "done": asyncio.Event()
            }

        for k, v in (context or {}).items():
            r = success(v)
            r["_execution_time"] = 0.0
            self.session_results[session_id][k] = r

        G = self.graphs[file_name]
        roots = [n for n in G.nodes if G.in_degree(n) == 0]

        for r in roots:
            self.event_queue.put_nowait((session_id, r))

    def push_event(self, session_id: str, node_name: str, value: Any):
        res = success(value)
        res["_execution_time"] = time.perf_counter()

        self.session_ctx[session_id][node_name] = value
        self.session_results[session_id][node_name] = res

        self.event_queue.put_nowait((session_id, node_name))