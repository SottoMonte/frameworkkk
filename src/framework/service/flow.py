import asyncio, time, json
import networkx as nx
from typing import Any, Callable, List, Dict, Optional
from datetime import datetime
from collections import defaultdict

# ── NodeResult ────────────────────────────────────────────────────────────────

_TAG = object()

def success(outputs, t0=None):
    return {"success": True,  "outputs": outputs, "errors": [],
            "time": _elapsed(t0), "_tag": _TAG}

def error(err, t0=None):
    return {"success": False, "outputs": None,
            "errors": err if isinstance(err, list) else [str(err)],
            "time": _elapsed(t0), "_tag": _TAG}

is_result = lambda v: isinstance(v, dict) and v.get("_tag") is _TAG
value_of  = lambda v: v["outputs"] if is_result(v) else v
_elapsed  = lambda t0: (time.perf_counter() - t0) if t0 else None

ok = success; fail = error; output = value_of

# ── MONITORING SYSTEM ────────────────────────────────────────────────────────

class DagMonitor:
    """Sistema di monitoraggio per il DAG"""
    
    def __init__(self):
        self.events = []
        self.metrics = defaultdict(lambda: {
            "executions": 0,
            "successes": 0,
            "failures": 0,
            "total_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0,
        })
        self.start_time = time.time()
    
    def log_event(self, event_type: str, node_name: str, data: dict = None):
        """Registra un evento"""
        self.events.append({
            "timestamp": time.time(),
            "type": event_type,
            "node": node_name,
            "data": data or {},
        })
    
    def record_execution(self, node_name: str, success: bool, duration: float):
        """Registra l'esecuzione di un nodo"""
        metrics = self.metrics[node_name]
        metrics["executions"] += 1
        if success:
            metrics["successes"] += 1
        else:
            metrics["failures"] += 1
        metrics["total_time"] += duration
        metrics["min_time"] = min(metrics["min_time"], duration)
        metrics["max_time"] = max(metrics["max_time"], duration)
    
    def get_report(self) -> dict:
        """Genera un report completo"""
        elapsed = time.time() - self.start_time
        return {
            "total_duration": elapsed,
            "total_events": len(self.events),
            "metrics": dict(self.metrics),
            "events_summary": self._summarize_events(),
        }
    
    def _summarize_events(self) -> dict:
        """Riassume gli eventi per tipo"""
        summary = defaultdict(int)
        for event in self.events:
            summary[event["type"]] += 1
        return dict(summary)
    
    def print_report(self):
        """Stampa un report leggibile"""
        report = self.get_report()
        print("\n" + "="*70)
        print("📊 MONITORING REPORT")
        print("="*70)
        print(f"\nTotal Duration: {report['total_duration']:.2f}s")
        print(f"Total Events: {report['total_events']}")
        print(f"\nEvent Summary: {report['events_summary']}")
        print(f"\nNode Metrics:")
        for node, metrics in report['metrics'].items():
            avg_time = metrics['total_time'] / metrics['executions'] if metrics['executions'] > 0 else 0
            print(f"  {node}:")
            print(f"    Executions: {metrics['executions']}")
            print(f"    Successes: {metrics['successes']}")
            print(f"    Failures: {metrics['failures']}")
            print(f"    Avg Time: {avg_time:.3f}s")
            print(f"    Min/Max: {metrics['min_time']:.3f}s / {metrics['max_time']:.3f}s")
        print("="*70 + "\n")

# ── CACHING SYSTEM ───────────────────────────────────────────────────────────

class DagCache:
    """Sistema di caching per i risultati dei nodi"""
    
    def __init__(self, ttl: float = 3600):
        self.ttl = ttl
        self.cache = {}
        self.timestamps = {}
    
    def get(self, key: str):
        """Recupera dal cache"""
        if key not in self.cache:
            return None
        
        if time.time() - self.timestamps[key] > self.ttl:
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        return self.cache[key]
    
    def set(self, key: str, value: Any):
        """Salva nel cache"""
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self):
        """Svuota il cache"""
        self.cache.clear()
        self.timestamps.clear()

# ── Nodo DAG ──────────────────────────────────────────────────────────────────

def node(name: str, fn: Callable, deps: List[str] = None, 
         schedule: float = None, duration: float = None,
         on_success: Callable = None, on_error: Callable = None, 
         on_start: Callable = None, triggers: List[str] = None,
         cache: bool = False, cache_ttl: float = 3600):
    """
    Crea un nodo nel DAG.
    
    Args:
        name: Nome univoco del nodo
        fn: Funzione async o sync da eseguire
        deps: Lista di dipendenze (nomi di altri nodi)
        schedule: Secondi tra esecuzioni ripetute
        duration: Secondi totali di esecuzione (con schedule)
        on_success: Callback(name, result, env) eseguito se il nodo ha successo
        on_error: Callback(name, error, env) eseguito se il nodo fallisce
        on_start: Callback(name, env) eseguito prima che il nodo parta
        triggers: Lista di nomi di nodi da eseguire quando QUESTO nodo ha successo
        cache: Se True, cache il risultato
        cache_ttl: Tempo di vita del cache (secondi)
    """
    return {
        "name": name, 
        "fn": fn, 
        "deps": deps or [], 
        "schedule": schedule, 
        "duration": duration,
        "on_success": on_success, 
        "on_error": on_error, 
        "on_start": on_start,
        "triggers": triggers or [],
        "cache": cache,
        "cache_ttl": cache_ttl,
    }

# ── NODE WRAPPERS (COMPOSABLE DECORATORS) ─────────────────────────────────────

def with_retry(n: dict, max_retries: int = 3, backoff: float = 1.0, 
               backoff_multiplier: float = 2.0, max_backoff: float = 60.0):
    """
    Wrapper che aggiunge retry automatico a un nodo.
    
    Uso:
        task_node = node("task", task_fn)
        retry_task = with_retry(task_node, max_retries=3)
    """
    async def retry_fn(env):
        attempt = 0
        last_error = None
        
        while attempt < max_retries + 1:
            try:
                result = await n["fn"](env) if asyncio.iscoroutinefunction(n["fn"]) else n["fn"](env)
                return result if is_result(result) else success(result)
            except Exception as e:
                attempt += 1
                last_error = e
                
                if attempt <= max_retries:
                    delay = backoff * (backoff_multiplier ** (attempt - 1))
                    delay = min(delay, max_backoff)
                    print(f"  ⚠️  {n['name']} fallito (tentativo {attempt}/{max_retries}), riprovando tra {delay:.1f}s...")
                    await asyncio.sleep(delay)
        
        return error(last_error)
    
    return node(
        f"{n['name']}_with_retry",
        retry_fn,
        deps=n["deps"],
        triggers=n["triggers"],
        on_success=n["on_success"],
        on_error=n["on_error"],
        on_start=n["on_start"],
    )

def with_cache(n: dict, cache_ttl: float = 3600):
    """
    Wrapper che aggiunge caching a un nodo.
    
    Uso:
        task_node = node("task", task_fn)
        cached_task = with_cache(task_node, cache_ttl=300)
    """
    node_copy = dict(n)
    node_copy["cache"] = True
    node_copy["cache_ttl"] = cache_ttl
    return node_copy

def with_timeout(n: dict, seconds: float = 5.0):
    """
    Wrapper che aggiunge timeout a un nodo.
    
    Uso:
        task_node = node("task", task_fn)
        timeout_task = with_timeout(task_node, seconds=10)
    """
    async def timeout_fn(env):
        try:
            result = await asyncio.wait_for(
                n["fn"](env) if asyncio.iscoroutinefunction(n["fn"]) else asyncio.sleep(0),
                timeout=seconds
            )
            return result if is_result(result) else success(result)
        except asyncio.TimeoutError:
            return error(f"Timeout after {seconds}s")
    
    return node(
        f"{n['name']}_with_timeout",
        timeout_fn,
        deps=n["deps"],
        triggers=n["triggers"],
        on_success=n["on_success"],
        on_error=n["on_error"],
        on_start=n["on_start"],
    )

def with_fallback(n: dict, fallback_fn: Callable):
    """
    Wrapper che aggiunge un fallback se il nodo fallisce.
    
    Uso:
        task_node = node("task", task_fn)
        safe_task = with_fallback(task_node, fallback_fn=lambda env: success("default"))
    """
    async def fallback_wrapper(env):
        try:
            result = await n["fn"](env) if asyncio.iscoroutinefunction(n["fn"]) else n["fn"](env)
            result = result if is_result(result) else success(result)
            
            if not result["success"]:
                # Se il nodo fallisce, usa il fallback
                fallback_result = await fallback_fn(env) if asyncio.iscoroutinefunction(fallback_fn) else fallback_fn(env)
                return fallback_result if is_result(fallback_result) else success(fallback_result)
            
            return result
        except Exception as e:
            # Se il nodo lancia un'eccezione, usa il fallback
            print(f"  ⚠️  Catturata eccezione, usando fallback")
            fallback_result = await fallback_fn(env) if asyncio.iscoroutinefunction(fallback_fn) else fallback_fn(env)
            return fallback_result if is_result(fallback_result) else success(fallback_result)
    
    return node(
        f"{n['name']}_with_fallback",
        fallback_wrapper,
        deps=n["deps"],
        triggers=n["triggers"],
        on_success=n["on_success"],
        on_error=n["on_error"],
        on_start=n["on_start"],
    )

def compose(*wrappers):
    """
    Componi multipli wrapper.
    
    Uso:
        task = node("task", task_fn)
        robust_task = compose(
            with_retry(task, max_retries=3),
            with_timeout(max_seconds=5),
            with_cache(cache_ttl=300)
        )
    
    Nota: Non funziona così! Vedi esempio sotto per il modo corretto.
    """
    pass

# ── Helpers ──────────────────────────────────────────────────────────────────

def _set_nested(d: dict, path: str, value):
    """Scrive value nel dict nested: "a.b.c" → d["a"]["b"]["c"] = value."""
    parts = path.split(".")
    cur   = d
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value

def _get_nested(d: dict, path: str, default=None):
    """Legge dal dict nested: "a.b.c" → d["a"]["b"]["c"]."""
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur: cur = cur[part]
        else: return default
    return cur

# ── Core Execution ────────────────────────────────────────────────────────────

async def _run_node(n, env, ctx, locks, monitor: DagMonitor = None, 
                    cache: DagCache = None):
    """Esegue un singolo nodo con supporto per callback e cache."""
    t0   = time.perf_counter()
    name = n["name"]
    failed = [d for d in n["deps"] if is_result(ctx.get(d)) and not ctx[d]["success"]]
    if failed:
        ctx[name] = error(f"dep failed: {', '.join(failed)}", t0)
        if monitor:
            monitor.log_event("dep_failed", name, {"failed_deps": failed})
        return
    
    # 🎯 CACHING
    if n.get("cache") and cache:
        cached = cache.get(name)
        if cached:
            ctx[name] = cached
            if monitor:
                monitor.log_event("cache_hit", name)
            return
    
    try:
        # 🎯 CALLBACK: on_start
        if n.get("on_start"):
            cb = n["on_start"]
            if asyncio.iscoroutinefunction(cb):
                await cb(name, env)
            else:
                cb(name, env)
        
        if monitor:
            monitor.log_event("start", name)
        
        r = await n["fn"](env) if asyncio.iscoroutinefunction(n["fn"]) else n["fn"](env)
        result = r if is_result(r) else success(r, t0)
        ctx[name] = result
        _set_nested(env, name, value_of(result))
        
        # 🎯 CACHING
        if n.get("cache") and cache and result["success"]:
            cache.set(name, result)
        
        # 🎯 CALLBACK: on_success
        if result["success"] and n.get("on_success"):
            cb = n["on_success"]
            if asyncio.iscoroutinefunction(cb):
                await cb(name, result, env)
            else:
                cb(name, result, env)
        
        if monitor:
            duration = time.perf_counter() - t0
            monitor.log_event("success", name, {"duration": duration})
            monitor.record_execution(name, True, duration)
    
    except Exception as e:
        ctx[name] = error(e, t0)
        
        # 🎯 CALLBACK: on_error
        if n.get("on_error"):
            cb = n["on_error"]
            if asyncio.iscoroutinefunction(cb):
                await cb(name, str(e), env)
            else:
                cb(name, str(e), env)
        
        if monitor:
            duration = time.perf_counter() - t0
            monitor.record_execution(name, False, duration)

 
async def _worker(q, env, ctx, nodes_map, locks, monitor: DagMonitor = None,
                  cache: DagCache = None):
    """Worker che elabora nodi dalla coda con supporto per triggers."""
    while True:
        name = await q.get()
        async with locks[name]:
            is_scheduled = nodes_map[name].get("schedule") is not None
            if is_scheduled or name not in ctx:
                await _run_node(nodes_map[name], env, ctx, locks, monitor, cache)
                
                # 🔔 EVENT TRIGGER
                if (is_result(ctx[name]) and ctx[name]["success"] and 
                    nodes_map[name].get("triggers")):
                    for triggered_name in nodes_map[name]["triggers"]:
                        if triggered_name in nodes_map:
                            triggerer_is_scheduled = nodes_map[name].get("schedule") is not None
                            if triggerer_is_scheduled:
                                ctx[triggered_name] = None
                            
                            await q.put(triggered_name)
                            if monitor:
                                monitor.log_event("trigger", triggered_name, 
                                               {"triggered_by": name})
        q.task_done()
 
async def _scheduler(name, n, q, monitor: DagMonitor = None):
    """Loop di scheduling per un singolo nodo."""
    start_time = time.perf_counter()
    duration = n.get("duration")
    schedule = n.get("schedule")
    
    if not schedule:
        return
    
    await q.put(name)
    
    while True:
        if duration and (time.perf_counter() - start_time) >= duration:
            break
        
        await asyncio.sleep(schedule)
        await q.put(name)
        if monitor:
            monitor.log_event("schedule", name)
 
async def run(nodes: List[Dict[str, Any]], env: dict = None, num_workers=3,
              enable_monitoring: bool = True, enable_caching: bool = True,
              cache_ttl: float = 3600):
    """
    Esegue un DAG di nodi con supporto completo.
    
    Args:
        nodes: Lista di nodi
        env: Environment iniziale
        num_workers: Numero di worker paralleli
        enable_monitoring: Abilita il monitoraggio
        enable_caching: Abilita il caching
        cache_ttl: TTL del cache
    
    Returns:
        (env, ctx, monitor) se monitoring abilitato, altrimenti (env, ctx)
    """
    G, nodes_map = nx.DiGraph(), {n["name"]: n for n in nodes}
    for n in nodes:
        G.add_node(n["name"])
        for d in n["deps"]: 
            G.add_edge(d, n["name"])
    
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Il grafo contiene cicli!")
    
    monitor = DagMonitor() if enable_monitoring else None
    cache = DagCache(ttl=cache_ttl) if enable_caching else None
    
    shared_env = dict(env or {})
    ctx = {}
    locks = {n["name"]: asyncio.Lock() for n in nodes}
    q = asyncio.Queue()
    
    ws = [asyncio.create_task(_worker(q, shared_env, ctx, nodes_map, locks, monitor, cache))
          for _ in range(num_workers)]
    
    scheduled_names = {n["name"] for n in nodes if n.get("schedule")}
    
    for gen in nx.topological_generations(G):
        for name in gen:
            await q.put(name)
            if monitor:
                monitor.log_event("queued", name, {"reason": "topological_sort"})
        if not any(n in scheduled_names for n in gen):
            await q.join()
    
    schedulers = [
        asyncio.create_task(_scheduler(n["name"], n, q, monitor))
        for n in nodes if n.get("schedule")
    ]
    
    try:
        await asyncio.gather(*schedulers)
    except asyncio.CancelledError:
        pass
    
    for w in ws: 
        w.cancel()
        try:
            await w
        except asyncio.CancelledError:
            pass
    
    if enable_monitoring:
        return shared_env, ctx, monitor
    else:
        return shared_env, ctx

# ── DSL compat ────────────────────────────────────────────────────────────────

def step(fn: Callable, *args, **kwargs): return (fn, args, kwargs)

async def act(s):
    t0 = time.perf_counter()
    if not isinstance(s, tuple): return error("invalid step", t0)
    fn, args, kwargs = s
    try:
        r = await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
        return r if is_result(r) else success(r, t0)
    except Exception as e:
        return error(e, t0)

# ── Wrappers ──────────────────────────────────────────────────────────────────

def retry(n, retries=3, delay=1):
    async def fn(env):
        for i in range(retries):
            try: return await n["fn"](env)
            except:
                if i == retries - 1: raise
                await asyncio.sleep(delay)
    return node(f"retry({n['name']})", fn, n["deps"])

def timeout(n, seconds=5):
    async def fn(env): return await asyncio.wait_for(n["fn"](env), seconds)
    return node(f"timeout({n['name']})", fn, n["deps"])

def catch(n, recovery=lambda env: None):
    async def fn(env):
        try: return await n["fn"](env)
        except: return await recovery(env)
    return node(f"catch({n['name']})", fn, n["deps"])

def pipeline(name, fns, deps=None):
    async def fn(env):
        data = env.get("kwargs")
        for f in fns:
            data = await f(data) if asyncio.iscoroutinefunction(f) else f(data)
            if is_result(data) and not data["success"]: return data
        return data
    return node(name, fn, deps or [])

def foreach(name, fn, data_dep=None):
    async def fn_(env):
        out = []
        for item in _get_nested(env, data_dep, []) if data_dep else []:
            r = await fn(item) if asyncio.iscoroutinefunction(fn) else fn(item)
            if is_result(r) and not r["success"]: return error(f"item {item}: {r['errors']}")
            out.append(r)
        return out
    return node(name, fn_, [data_dep] if data_dep else [])

def switch(name, cases, deps=None):
    async def fn(env):
        for cond, act in cases:
            if (cond(env) if callable(cond) else cond):
                return await act(env) if asyncio.iscoroutinefunction(act) else act(env)
    return node(name, fn, deps or [])

# ── DAG su AST ────────────────────────────────────────────────────────────────
#
# run_ast riceve gli item AST di un dict direttamente dall'interprete,
# analizza chiavi e dipendenze, costruisce il grafo ed esegue in parallelo.
# L'interprete non fa pre-processing: passa solo items, env e visit.

def _keys_of(n) -> list:
    if not isinstance(n, dict): return []
    t = n.get("type")
    if t == "declaration":
        tgt = n.get("target", {})
        if tgt.get("type") == "pair":
            name = tgt.get("value", {}).get("name")
            return [name] if name else []
        return _keys_of(tgt)
    if t == "pair":
        k  = n.get("key", {})
        kn = k.get("value") if k.get("type") == "string" else k.get("name")
        return [kn] if kn else []
    if t in ("var", "identifier"):
        return [n["name"]]
    if t in ("sequence", "tuple", "list", "dict"):
        return [k for x in n.get("items", []) for k in _keys_of(x)]
    return []

def _deps_of(n) -> set:
    if not isinstance(n, dict): return set()
    t = n.get("type")
    if t in ("number", "string", "bool", "any", "context_var",
             "function_def", "function_value"):
        return set()
    if t in ("var", "identifier"):
        return {n["name"].split(".")[0]}
    if t == "call":
        d = {n["name"].split(".")[0]} if n.get("name") else set()
        d |= set().union(*(_deps_of(a) for a in n.get("args", [])))
        d |= set().union(*(_deps_of(v) for v in n.get("kwargs", {}).values()))
        return d
    if t == "binop":       return _deps_of(n["left"]) | _deps_of(n["right"])
    if t == "not":         return _deps_of(n["value"])
    if t == "pipe":        return set().union(*(_deps_of(s) for s in n.get("steps", [])))
    if t in ("pair", "declaration"):
        return _deps_of(n["value"])
    if t in ("tuple", "list", "sequence", "dict"):
        return set().union(*(_deps_of(i) for i in n.get("items", [])))
    return set()

async def run_ast(items: list, env: dict, visit) -> tuple:
    """Esegue una lista di item AST con parallelismo DAG.

    items  — item AST di un dict (top-level o annidato)
    env    — contesto padre (sola lettura: viene copiato)
    visit  — coroutine  visit(node, env) → (key, val), env  dell'interprete

    Ritorna (result, errors):
      result — dict {nome: valore} per i nodi riusciti
      errors — dict {nome: str}   per i nodi falliti
    """
    defined  = {k for it in items for k in _keys_of(it)}
    item_of  = {k: it for it in items for k in _keys_of(it)}
    if not defined:
        return {}, {}

    G = nx.DiGraph()
    for k in defined:
        G.add_node(k)
    for k, it in item_of.items():
        for d in _deps_of(it):
            if d in defined and d != k:
                G.add_edge(d, k)
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Ciclo di dipendenze nel dict")

    local   = dict(env)
    results = {}
    errors  = {}

    async def eval_node(name):
        failed = [d for d in G.predecessors(name) if d in errors]
        if failed:
            errors[name] = f"dep failed: {', '.join(failed)}"
            return
        try:
            (key, val), _ = await visit(item_of[name], local)
            if isinstance(key, tuple):
                for k, v in zip(key, val):
                    results[k] = v
                    local[k]   = v
            else:
                results[name] = val
                local[name]   = val
        except Exception as e:
            errors[name] = str(e)

    for generation in nx.topological_generations(G):
        await asyncio.gather(*(eval_node(name) for name in generation))

    return results, errors
