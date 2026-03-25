"""
DAG Engine v7 - SESSION-AWARE + FRESHNESS FIXED + LIFECYCLE HOOKS
"""

import asyncio
import inspect
from typing import Any, Callable, List, Dict, Optional, Tuple
import networkx as nx
import time
from collections import ChainMap
from collections.abc import Mapping
import traceback
import functools

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

def action(custom_filename: str = __file__, app_context=None, **constants):
    def decorator(function):
        if asyncio.iscoroutinefunction(function):
            @functools.wraps(function)
            async def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = await function(*args, **kwargs)
                    return success(result, start_time)
                except Exception as e:
                    return error(e, start_time)
            return wrapper
        else:
            @functools.wraps(function)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = function(*args, **kwargs)
                    return success(result, start_time)
                except Exception as e:
                    return error(e, start_time)
            return wrapper
    return decorator


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
    meta = node_def.get("meta", False)
    node_path = node_def.get("path") or node_def["name"]
    node_meta = {"path": node_path, "session_id": session_id} if session_id else {"path": node_path}

    parent_path = ".".join(node_path.split(".")[:-1])
    parent_scope = scheme.get(ctx, parent_path) if parent_path else {}
    if not isinstance(parent_scope, Mapping): parent_scope = {}

    view_parts = [node_meta, parent_scope, ctx]
    if isinstance(meta, list):
        view_parts.insert(1, {md: results[md] for md in meta if md in results})
    elif meta:
        view_parts.insert(1, dict(results))

    return ChainMap(*view_parts)

def _parse_policy(policy) -> Tuple:
    if policy == "all":
        return ("all", None)
    if policy == "any":
        return ("any", None)
    if isinstance(policy, int) and policy >= 1:
        return ("quorum", policy)
    raise ValueError(f"deps_policy non valida: {policy!r}")

# -- LIFECYCLE HOOK RUNNER ------------------------------------------------------

async def _fire_hook(hook, view, result=None, *, runner=None, session_id=None, node_def=None):
    """
    Esegue un lifecycle hook in modo sicuro. Supporta due forme:

      - stringa  → triggera il nodo con quel nome nella sessione corrente,
                   iniettando il result nel context prima di triggerare
      - callable → chiamato con (view) oppure (view, result) in base alla firma
    """
    if hook is None:
        return

    try:
        # -- forma stringa: triggera un nodo nel DAG --
        if isinstance(hook, str):
            if runner is None or session_id is None:
                return
            # push_event inietta result come valore del nodo stesso,
            # così il nodo hook lo riceve pulito nel proprio view
            # es: view["outputs"], view["success"], view["errors"]
            # Inietta nel result chi ha triggerato questo hook
            payload = dict(result) if result is not None else {}
            payload["trigger"] = node_def["name"] if node_def else None
            runner.push_event(session_id, hook, payload)
            return

        # -- forma callable --
        sig = inspect.signature(hook)
        params = list(sig.parameters)
        if result is not None and len(params) >= 2:
            await _call_if_coro(hook, view, result)
        else:
            await _call_if_coro(hook, view)

    except Exception:
        # I lifecycle hook non devono mai far crashare il nodo
        pass


# -- NODE DEFINITION ------------------------------------------------------------

def node(name: str, fn: Callable, **kwargs) -> Dict[str, Any]:
    _parse_policy(kwargs.get("deps_policy", "all"))
    return {
        "name":               name,
        "fn":                 fn,
        "deps":               kwargs.get("deps", []),
        "deps_policy":        kwargs.get("deps_policy", "all"),
        "ignore_failed_deps": kwargs.get("ignore_failed_deps", False),
        "meta":               kwargs.get("meta", False),
        "schedule":           kwargs.get("schedule"),
        "duration":           kwargs.get("duration"),
        # --- Lifecycle hooks ---
        "on_start":           kwargs.get("on_start"),    # chiamato prima dell'esecuzione
        "on_success":         kwargs.get("on_success"),  # chiamato se il nodo ha successo
        "on_error":           kwargs.get("on_error"),    # chiamato se il nodo fallisce
        "on_close":           kwargs.get("on_close"),    # chiamato sempre alla fine (success o error)
        "on_end":             kwargs.get("on_end"),      # chiamato quando il nodo termina
        # -----------------------
        "when":               kwargs.get("when"),
        "timeout":            kwargs.get("timeout"),
        "retries":            kwargs.get("retries", 0),
        "retry_delay":        kwargs.get("retry_delay", 0),
        "path":               kwargs.get("path"),
        "default":            kwargs.get("default"),
    }

# -- CORE CHECKS ----------------------------------------------------------------

async def _check_deps(node_def, results, state, t0, ctx):
    deps = node_def.get("deps", [])
    if not deps:
        return True, False

    mode, quorum_n = _parse_policy(node_def.get("deps_policy", "all"))
    last_check = state["last_check"]
    ignore_failed = node_def.get("ignore_failed_deps", False)

    def _is_ok(d):
        if d in results:
            res_d = results[d]
            if not (ignore_failed or res_d["success"]):
                return False
            if res_d.get("_static"):
                return True
            return res_d.get("_execution_time", 0.0) > last_check
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

async def _execute(node_def, ctx, results, view, t0, *, runner=None, session_id=None):
    """
    Esegue fn con supporto a retries, timeout e lifecycle hooks completi:
      on_start   → prima dell'esecuzione
      on_success → se il nodo termina con successo
      on_error   → se il nodo fallisce (anche dopo tutti i retry)
      on_close   → sempre, al termine (sia success che error)

    I hooks accettano:
      - stringa  → nome di un nodo da triggerare nella sessione corrente
      - callable → fn(view) oppure fn(view, result)
    """
    node_name   = node_def["name"]
    node_path   = node_def.get("path") or node_name
    retries     = node_def.get("retries", 0)
    retry_delay = node_def.get("retry_delay", 0)
    timeout     = node_def.get("timeout")
    hook_kw = {"runner": runner, "session_id": session_id, "node_def": node_def}

    # --- on_start ---
    await _fire_hook(node_def.get("on_start"), view, **hook_kw)

    result = None

    for attempt in range(retries + 1):
        try:
            if timeout:
                r = await asyncio.wait_for(_call_if_coro(node_def["fn"], view), timeout=timeout)
            else:
                r = await _call_if_coro(node_def["fn"], view)

            result = r if is_result(r) else success(r, t0)
            break  # successo: usciamo dal loop retry

        except asyncio.TimeoutError:
            result = error(f"timeout after {timeout}s (attempt {attempt+1})", t0)
        except Exception as e:
            result = error(e, t0)

        if attempt < retries:
            await asyncio.sleep(retry_delay)

    result["_execution_time"] = time.perf_counter()

    # --- on_success / on_error ---
    if result["success"]:
        await _fire_hook(node_def.get("on_success"), view, result, **hook_kw)
    else:
        await _fire_hook(node_def.get("on_error"), view, result, **hook_kw)

    # --- on_close: chiamato SEMPRE, sia success che error ---
    await _fire_hook(node_def.get("on_close"), view, result, **hook_kw)

    # Aggiorna context e results
    _set_path(ctx, node_path, result["outputs"])
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
            results[node_name] = error(f"WHEN condition error: {e}", t0)
            state["done"].set()
            return

        if not should_run:
            res = success(None, t0)
            res["_skipped"] = True
            res["_execution_time"] = time.perf_counter()
            results[node_name] = res

            # Notifica successori anche se saltato
            for succ in runner.graphs[file_name].successors(node_name):
                await runner.event_queue.put((session_id, succ))

            state["done"].set()
            return

    result = await _execute(node_def, ctx, results, view, t0, runner=runner, session_id=session_id)

    # Notifica successori
    for succ in runner.graphs[file_name].successors(node_name):
        await runner.event_queue.put((session_id, succ))

    # Rescheduling
    if node_def.get("schedule"):
        if state["start_time"] is None:
            state["start_time"] = time.perf_counter()

        duration = node_def.get("duration")
        async def resched():
            await asyncio.sleep(node_def["schedule"])
            
            should_terminate = False
            if duration is not None:
                elapsed = time.perf_counter() - state["start_time"]
                if elapsed >= duration:
                    should_terminate = True

            if should_terminate:
                # ESEGUIAMO ON_END SOLO QUI (FINE VITA)
                last_res = results.get(node_name)
                await _fire_hook(
                    node_def.get("on_end"), 
                    view, 
                    last_res, 
                    runner=runner, 
                    session_id=session_id, 
                    node_def=node_def
                )
                return
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

        for sid, fname in self.session_files.items():
            if fname == file_name:
                for n_name in self.files[file_name]:
                    if n_name not in self.session_node_state[sid]:
                        self.session_node_state[sid][n_name] = {
                            "last_check": -1.0,
                            "done":       asyncio.Event(),
                            "start_time": None,
                        }

    def create_session(self, session_id: str, file_name: str, context=None):
        self.session_ctx[session_id]     = dict(context or {})
        self.session_results[session_id] = {}
        self.session_files[session_id]   = file_name
        self.session_node_state[session_id] = {}

        for n in self.files[file_name]:
            node_def = self.nodes_map[file_name][n]
            if node_def.get("default") is not None:
                node_path = node_def.get("path") or n
                _set_path(self.session_ctx[session_id], node_path, node_def["default"])

        for n in self.files[file_name]:
            self.session_node_state[session_id][n] = {
                "last_check": -1.0,
                "done":       asyncio.Event(),
                "start_time": None,
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

    async def run_node(self, node_def: Dict, context: Dict):
        """Esegue un nodo immediatamente usando la logica dell'engine."""
        t0 = time.perf_counter()
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

@action()
async def sentry(context=dict(), condition=lambda x: False):
    print("Sentry", context, condition)
    if condition(**context):
        return True
    else:
        return False

async def branch(condition,context, branchs):
    #print("##############", context, condition,condition(**context),"\n\n")
    if isinstance(condition, bool):
        check = condition
    else:
        check = condition(**context)
    if check:
        return branchs[True]
    else:
        return branchs[False]

async def when(condition, step, context=dict()):
    # Se la condizione (funzione o booleano) è vera, esegue lo step
    should_run = await sentry(context, condition)
    if should_run.get('success', False):
        return await act(step, context)
    else:
        return should_run

def foreach(iterable, fn,args=()):
    """
    Esegue fn per ogni elemento dell'iterabile.
    Restituisce una lista di risultati.
    """
    async def _fn(view):
        items = view.get("items") or iterable
        
        results = []
        for arg in args:
            for item in items:
                #new_view = ChainMap(view, {"item": item})
                res = await _call_if_coro(fn, view,arg)
                results.append(res)
        print("results", results)
        return results
    return _fn

def pipeline(iterable, acts, *args, **kwargs):
    """
    Esegue fn per ogni elemento dell'iterabile.
    Restituisce una lista di risultati.
    """
    async def _fn(view):
        result = view.get("items") or iterable
        
        for arg in args:
            result = await act(step(acts,result,*arg))
            
            if not result["success"]:
                return result
            result = result.get("outputs")
        print("results", result)
        return result
    return _fn

def reset(data,new):
    return new

async def parallel(dato,*acts):
    """
    Crea una pipeline di step.
    Supporta:
      - pipeline(steps) -> factory che ritorna node_fn(ctx)
      - pipeline(data, steps) -> esecuzione immediata (utile in |>)
    """
    tasks = []
    for act in acts:
        tasks.append(act)
    return await asyncio.gather(*tasks)

async def pipeline2(steps):
    """
    Crea una pipeline di step.
    Supporta:
      - pipeline(steps) -> factory che ritorna node_fn(ctx)
      - pipeline(data, steps) -> esecuzione immediata (utile in |>)
    """
    result = steps[0]
    for step in steps[1:]:
        result = await act(step(result))
        if not result["success"]:
            return result
    return result

async def switch(data, cases):
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

    #print("################", data, cases, "\n\n")

    for cond, fn in cases.items():
        #print("################", type(cond), cond, fn, "\n\n")
        if cond is True:
            continue
        if not callable(cond):
            continue
        elif "ContextVar" in str(type(cond)):
            condizione = cond(**data)
            check = condizione(**data)
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
            print(errore_completo, "e")
            raise RuntimeError(f"switch condition error: {e}")

    if default_fn:
        if callable(default_fn):
            a, _ = await _call_if_coro(default_fn, data)
            return a
        else:
            return default_fn

    return None