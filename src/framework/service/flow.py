"""
DAG Engine v7 - FRESHNESS-BASED DEPENDENCIES
- Rimosso: cycle tracking (_cycle)
- Aggiunto: timestamp-based freshness check
- Ogni nodo ha _execution_time: quando è stato eseguito l'ultima volta
- Un successore riparte se ALMENO UNA sua dep è "fresca" (timestamp > suo ultimo check)
- Nessun gate/queue complicato: pura logica di scheduling
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

def _get_node_view(node_def, ctx, results):
    """
    Costruisce la view per il nodo.
    Se meta_deps è vuoto, ritorna ctx.
    Se ci sono meta_deps, ritorna una ChainMap con i risultati completi davanti.
    """
    meta_deps = node_def.get("meta_deps", [])
    if not meta_deps:
        return ctx
    meta_subset = {md: results[md] for md in meta_deps if md in results}
    return ChainMap(meta_subset, ctx)

def _parse_policy(policy) -> Tuple:
    """Parsa 'all', 'any', o numero intero >= 1 (per quorum)"""
    if policy == "all":
        return ("all", None)
    if policy == "any":
        return ("any", None)
    if isinstance(policy, int):
        if policy >= 1:
            return ("quorum", policy)
        raise ValueError(f"deps_policy come numero deve essere >= 1, ricevuto: {policy}")
    raise ValueError(
        f"deps_policy non valida: {policy!r}. "
        f"Valori accettati: 'all', 'any', o numero intero >= 1"
    )

# -- FRESHNESS LOGIC (core del nuovo approccio) --------------------------------

def _get_dep_freshness(dep_name: str, results: dict) -> Tuple[bool, float]:
    """
    Ritorna (has_result, execution_time).
    execution_time è il timestamp (perf_counter) dell'ultima esecuzione.
    """
    if dep_name not in results:
        return False, 0.0
    res = results[dep_name]
    exec_time = res.get("_execution_time", 0.0)
    return True, exec_time

def _is_dep_satisfied(dep_name: str, results: dict, node_last_check: float, mode: str, quorum_n: Optional[int]) -> bool:
    """
    Verifica se UNA dep è soddisfatta (has result + successful + fresh).
    
    Una dep è "fresca" se:
    - Ha un risultato eseguito
    - Il suo execution_time > node_last_check
    
    Per policy 'all': tutte le deps devono essere fresche + successful
    Per policy 'any': almeno una deve essere fresca + successful
    Per policy 'quorum(N)': almeno N devono essere fresche + successful
    """
    has_result, exec_time = _get_dep_freshness(dep_name, results)
    if not has_result:
        return False
    res = results[dep_name]
    # Deve essere successful E fresco
    return res.get("success", False) and (exec_time > node_last_check)

# -- NODE DEFINITION ------------------------------------------------------------

def node(name: str, fn: Callable, **kwargs) -> Dict[str, Any]:
    """
    Crea un nodo DAG.

    Parametri:
        name        : identificatore univoco del nodo
        fn          : funzione (sync o async), riceve la view come unico argomento
        deps        : lista di nodi da cui dipende
        deps_policy : "all" (default) | "any" | numero intero >= 1 (quorum)
        meta        : nodi di cui ricevere il result completo nella view
        schedule    : intervallo in secondi per riesecuzione automatica
        duration    : durata massima in secondi dello scheduling
        when        : condizione booleana - se False il nodo viene saltato
        timeout     : timeout in secondi per l'esecuzione
        retries     : tentativi in caso di errore (default 0)
        retry_delay : attesa in secondi tra retry (default 0)
        on_start    : hook -> fn(name, view)
        on_success  : hook -> fn(name, result, view)
        on_error    : hook -> fn(name, err_msg, view)
    
    Esempi:
        node("step", fn, deps=["a", "b"], deps_policy="all")      # Entrambi
        node("step", fn, deps=["a", "b"], deps_policy="any")      # Uno almeno
        node("step", fn, deps=["a", "b", "c"], deps_policy=2)     # Almeno 2
    """
    policy = kwargs.get("deps_policy", "all")
    _parse_policy(policy)

    return {
        "name":        name,
        "fn":          fn,
        "deps":        kwargs.get("deps", []),
        "deps_policy": policy,
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

# -- CHECK DEPS (semplificato con freshness) -----------------------------------

async def _check_deps(node_def, results, t0) -> Tuple[bool, bool]:
    """
    Verifica se le deps sono soddisfatte secondo deps_policy e freschezza.
    
    Restituisce (ok, fatal):
      (True,  False) -> policy soddisfatta, procedi
      (False, False) -> non ancora soddisfatta, aspetta
      (False, True)  -> errore fatale: una dep è fallita (policy 'all' + dep failed)
    """
    deps = node_def.get("deps", [])
    if not deps:
        return True, False

    mode, quorum_n = _parse_policy(node_def.get("deps_policy", "all"))
    node_last_check = node_def.get("_last_check_time", 0.0)

    # Verifica freschezza
    fresh_ok  = [d for d in deps if _is_dep_satisfied(d, results, node_last_check, mode, quorum_n)]
    
    # Conta i risultati esistenti (non importa freschezza)
    existing = [d for d in deps if d in results]
    failed = [d for d in existing if not results[d]["success"]]

    if mode == "all":
        # Tutti devono essere freshi + successful
        # Se uno è fallito, errore fatale
        if failed:
            results[node_def["name"]] = error(f"dep failed: {', '.join(failed)}", t0)
            return False, True
        # Se non tutti sono freschi, aspetta
        if len(fresh_ok) < len(deps):
            return False, False
        return True, False

    elif mode == "any":
        # Almeno uno deve essere fresco + successful
        if len(fresh_ok) >= 1:
            return True, False
        # Se nessuno è fresco ma tutti sono failed, errore fatale
        if len(existing) == len(deps) and len(failed) == len(deps):
            results[node_def["name"]] = error(f"all deps failed: {', '.join(failed)}", t0)
            return False, True
        return False, False

    elif mode == "quorum":
        # Almeno N devono essere freshi + successful
        if len(fresh_ok) >= quorum_n:
            return True, False
        # Se abbiamo meno deps fresche che quorum richiede, aspetta
        return False, False

    return False, False

async def _check_condition(node_def, view, results, t0) -> bool:
    when_fn = node_def.get("when")
    if when_fn:
        try:
            return await _call_if_coro(when_fn, **view)
        except Exception as e:
            results[node_def["name"]] = error(f"Condition 'when' failed: {e}", t0)
            return False
    return True

async def _run_hook(node_def, view, hook_name, extra_arg=None):
    hook = node_def.get(hook_name)
    if not hook:
        return
    name = node_def["name"]
    if extra_arg is not None:
        await _call_if_coro(hook, name, extra_arg, view)
    else:
        await _call_if_coro(hook, name, view)

async def _execute_with_retry(node_def, ctx, results, view, t0):
    retries = node_def.get("retries", 0)
    delay   = node_def.get("retry_delay", 0)
    for attempt in range(retries + 1):
        try:
            return await _call_node_fn(node_def, ctx, results, view, t0)
        except Exception as e:
            if attempt < retries:
                if delay > 0:
                    await asyncio.sleep(delay)
                continue
            res = error(e, t0)
            ctx[node_def["name"]]     = None
            results[node_def["name"]] = res
            return res

async def _call_node_fn(node_def, ctx, results, view, t0):
    name    = node_def["name"]
    timeout = node_def.get("timeout")
    if timeout:
        r = await asyncio.wait_for(_call_if_coro(node_def["fn"], view), timeout=timeout)
    else:
        r = await _call_if_coro(node_def["fn"], view)
    result = r if is_result(r) else success(r, t0)
    # Salviamo il timestamp di esecuzione per la freschezza
    result["_execution_time"] = time.perf_counter()
    ctx[name]     = result["outputs"]
    results[name] = result
    return result

async def _trigger_successors(node_def, result, results, nodes_map, queue):
    """
    Accoda i successori se la loro deps_policy è soddisfatta.
    Con freschezza, i successori si accoderanno automaticamente quando
    vedranno dati freschi.
    """
    if not result["success"]:
        # Se il nodo è fallito, accoda i successori perché controllino
        # la loro policy (es. policy 'any' potrebbe essere soddisfatta da altri)
        pass

    for succ_name in node_def.get("_successors", []):
        succ_def = nodes_map.get(succ_name)
        if not succ_def:
            continue

        if not queue:
            continue

        # Semplice: accoda il successore
        # Il successore stesso controllerà freschezza in _check_deps
        try:
            queue.put_nowait(succ_name)
        except asyncio.QueueFull:
            await queue.put(succ_name)

async def _handle_scheduling(node_def, ctx, results, queue, nodes_map=None):
    """
    Gestisce il reschedule del nodo.
    """
    name     = node_def["name"]
    schedule = node_def.get("schedule")
    duration = node_def.get("duration")

    if not schedule or not queue:
        return

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
        async def reschedule_task(node_name=name):
            await asyncio.sleep(schedule)
            if not queue:
                return
            try:
                queue.put_nowait(node_name)
            except asyncio.QueueFull:
                await queue.put(node_name)
        asyncio.create_task(reschedule_task())
    elif "_schedule_start" in ctx and name in ctx["_schedule_start"]:
        del ctx["_schedule_start"][name]

# -- CORE EXECUTION -------------------------------------------------------------

async def _run_node(node_def, ctx, results, locks, nodes_map, queue=None):
    """
    Esegui il nodo se le sue deps sono soddisfatte.
    
    Basato su freschezza:
    - Se le deps non sono fresche, torna subito (non aspettare)
    - Se sono fresche, esegui il nodo
    - Aggiorna _last_check_time per la freschezza
    """
    t0 = time.perf_counter()

    def _set_done():
        ev = node_def.get("_done_event")
        if ev:
            ev.set()

    # Verifica deps con freschezza
    deps_ok, fatal = await _check_deps(node_def, results, t0)
    if not deps_ok:
        # Salva quando abbiamo fatto l'ultimo check
        node_def["_last_check_time"] = t0
        if fatal:
            _set_done()
        return

    # Aggiorna il check time prima di eseguire
    node_def["_last_check_time"] = t0

    view = _get_node_view(node_def, ctx, results)
    if not await _check_condition(node_def, view, results, t0):
        await _handle_scheduling(node_def, ctx, results, queue, nodes_map)
        _set_done()
        return

    await _run_hook(node_def, view, "on_start")
    result = await _execute_with_retry(node_def, ctx, results, view, t0)

    if result["success"]:
        await _run_hook(node_def, view, "on_success", result)
    else:
        err_msg = ", ".join(result["errors"])
        await _run_hook(node_def, view, "on_error", err_msg)

    # Accoda i successori
    await _trigger_successors(node_def, result, results, nodes_map, queue)

    # Gestisci reschedule
    await _handle_scheduling(node_def, ctx, results, queue, nodes_map)

    _set_done()

# -- DAGRUNNER ------------------------------------------------------------------

class DagRunner:
    """DAG Runner v7 — Freshness-based dependencies"""

    def __init__(self, num_workers: int = 3):
        self.num_workers       = num_workers
        self.nodes_map         = {}
        self.context_by_file   = {}
        self.results_by_file   = {}
        self.files             = {}
        self.graphs            = {}
        self.q                 = None
        self.locks             = {}
        self.tasks             = []
        self._running          = False
        self._stop_event       = None

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
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

                if node_name is None:
                    self.q.task_done()
                    break

                try:
                    if node_name not in self.nodes_map:
                        continue
                    file_name = self._find_file_for_node(node_name)
                    if not file_name:
                        continue
                    async with self.locks[node_name]:
                        node_def = self.nodes_map[node_name]
                        ctx      = self.context_by_file[file_name]
                        results  = self.results_by_file[file_name]
                        await _run_node(node_def, ctx, results, self.locks, self.nodes_map, self.q)
                finally:
                    self.q.task_done()
        except asyncio.CancelledError:
            pass

    async def start(self):
        if self._running:
            return
        self._running    = True
        self._stop_event = asyncio.Event()
        self.q           = asyncio.Queue()
        for i in range(self.num_workers):
            self.tasks.append(asyncio.create_task(self._worker(i)))

    async def stop(self):
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

    async def add_file(self, file_name: str, nodes: List[Dict], context: dict = None):
        G = nx.DiGraph()
        for n in nodes:
            name = n["name"]
            self.nodes_map[name] = n
            self.locks[name]     = asyncio.Lock()
            n["_done_event"]     = asyncio.Event()
            n["_last_check_time"] = 0.0
            G.add_node(name)
            for d in n.get("deps", []):
                G.add_edge(d, name)

        if not nx.is_directed_acyclic_graph(G):
            raise ValueError(f"File '{file_name}': il DAG contiene cicli!")

        for n_name in G.nodes:
            if n_name in self.nodes_map:
                self.nodes_map[n_name]["_successors"] = list(G.successors(n_name))

        self.files[file_name]           = [n["name"] for n in nodes]
        self.context_by_file[file_name] = dict(context or {})
        self.results_by_file[file_name] = {}
        self.graphs[file_name]          = G

        res_dict = self.results_by_file[file_name]
        for k, v in (context or {}).items():
            r = success(v)
            r["time"]   = 0.0
            r["_execution_time"] = 0.0
            res_dict[k] = r

        if self._running and self.q:
            # Accoda solo i nodi radice (senza deps)
            roots = [n for n in G.nodes if G.in_degree(n) == 0]
            for name in roots:
                if name in self.files[file_name]:
                    try:
                        self.q.put_nowait(name)
                    except asyncio.QueueFull:
                        await self.q.put(name)

    def get_file_context(self, file_name: str) -> dict:
        ctx = dict(self.context_by_file.get(file_name, {}))
        return {k: v for k, v in ctx.items() if not k.startswith("_")}

    def get_file_results(self, file_name: str) -> dict:
        return dict(self.results_by_file.get(file_name, {}))

    def file_status(self, file_name: str) -> dict:
        nodes    = self.files.get(file_name, [])
        results  = self.results_by_file.get(file_name, {})
        executed = sum(1 for n in nodes if n in results)
        ok_count = sum(1 for n in nodes if n in results and results[n]["success"])
        return {
            "total":      len(nodes),
            "executed":   executed,
            "successful": ok_count,
            "pending":    len(nodes) - executed,
            "failed":     executed - ok_count,
        }

    async def wait_file(self, file_name: str):
        nodes = self.files.get(file_name, [])
        if not nodes:
            return
        await asyncio.gather(*(
            self.nodes_map[n]["_done_event"].wait()
            for n in nodes if n in self.nodes_map
        ))

    async def wait_node(self, file_name: str, node_name: str):
        if node_name in self.nodes_map:
            await self.nodes_map[node_name]["_done_event"].wait()

    def get_all_contexts(self) -> dict:
        return {f: self.get_file_context(f) for f in self.files}