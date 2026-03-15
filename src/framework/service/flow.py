import asyncio, inspect, time
import networkx as nx
from typing import Any, Callable, List, Dict

# ---------------------------------------------------------------------------
# Risultato di un nodo — dict puro con sentinel privato
#
# _FLOW è un object() singleton: mai esposto, impossibile da produrre
# accidentalmente nei dati utente. is_result() usa `is`, non ==.
# ---------------------------------------------------------------------------

_FLOW = object()

def success(outputs, start_time=None):
    return {"success": True,  "outputs": outputs, "errors": [],
            "time": _t(start_time), "_tag": _FLOW}

def error(err, start_time=None):
    return {"success": False, "outputs": None,
            "errors": [str(err)] if not isinstance(err, list) else err,
            "time": _t(start_time), "_tag": _FLOW}

def is_result(v) -> bool: return isinstance(v, dict) and v.get("_tag") is _FLOW
def value_of(v):          return v["outputs"] if is_result(v) else v
def errors_of(v) -> list: return v["errors"]  if is_result(v) else []

def _t(t0): return (time.perf_counter() - t0) if t0 else None

# back-compat
ok     = success
fail   = error
output = value_of

# ---------------------------------------------------------------------------
# Nodo DAG
# ---------------------------------------------------------------------------

def node(name: str, fn: Callable, deps: List[str] = None,
         params: dict = None, schedule: float = None, event_trigger: Callable = None):
    deps, params = deps or [], params or {}
    pos   = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    names = [n for n, p in inspect.signature(fn).parameters.items() if p.kind in pos]
    return {
        "name": name, "fn": fn, "deps": deps, "params": params,
        "arg_map": {d: names[i] for i, d in enumerate(deps) if i < len(names)},
        "schedule": schedule, "event_trigger": event_trigger,
    }

# ---------------------------------------------------------------------------
# Wrapper nodi
# ---------------------------------------------------------------------------

def retry(n, retries=3, delay=1):
    async def fn(**kw):
        for i in range(retries):
            try:    return await _call(n["fn"], kw)
            except:
                if i == retries - 1: raise
                await asyncio.sleep(delay)
    return node(f"retry({n['name']})", fn, n["deps"])

def timeout(n, seconds=5):
    async def fn(**kw): return await asyncio.wait_for(_call(n["fn"], kw), seconds)
    return node(f"timeout({n['name']})", fn, n["deps"])

def catch(n, recovery=lambda **kw: None):
    async def fn(**kw):
        try:    return await _call(n["fn"], kw)
        except: return await _call(recovery, kw)
    return node(f"catch({n['name']})", fn, n["deps"])

def pipeline(name, fns, deps=None):
    async def fn(**kw):
        data = kw.get("kwargs")
        for f in fns:
            data = await _call(f, data)
            if is_result(data) and not data["success"]: return data
        return data
    return node(name, fn, deps or [])

def foreach(name, fn, data_dep=None):
    async def node_fn(**kw):
        out = []
        for item in kw.get("kwargs", []):
            r = await _call(fn, item)
            if is_result(r) and not r["success"]: return error(f"item {item}: {r['errors']}")
            out.append(r)
        return out
    return node(name, node_fn, [data_dep] if data_dep else [])

def switch(name, cases, deps=None):
    async def fn(**kw):
        for cond, act in cases:
            if (cond(**kw) if callable(cond) else cond):
                return await _call(act, kw)
    return node(name, fn, deps or [])

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

async def _call(fn, arg):
    if asyncio.iscoroutinefunction(fn):
        return await fn(**arg) if isinstance(arg, dict) else await fn(arg)
    return fn(**arg) if isinstance(arg, dict) else fn(arg)

async def _run_node(n, ctx):
    t0      = time.perf_counter()
    deps    = n["deps"]
    arg_map = n["arg_map"]

    failed = [d for d in deps if is_result(ctx.get(d)) and not ctx[d]["success"]]
    if failed:
        ctx[n["name"]] = error(f"dep failed: {', '.join(failed)}", t0); return

    kw = {**n["params"], **{arg_map.get(d, d): value_of(ctx[d]) for d in deps}}
    try:
        r = await _call(n["fn"], kw)
        ctx[n["name"]] = r if is_result(r) else success(r, t0)
    except Exception as e:
        ctx[n["name"]] = error(e, t0)

async def _worker(q, ctx, nodes_map, locks):
    while True:
        name = await q.get()
        async with locks[name]:
            if name not in ctx:
                await _run_node(nodes_map[name], ctx)
        q.task_done()

async def run(nodes: List[Dict[str, Any]], num_workers=3):
    G = nx.DiGraph()
    nodes_map = {n["name"]: n for n in nodes}
    for n in nodes:
        G.add_node(n["name"])
        for d in n["deps"]: G.add_edge(d, n["name"])
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Il grafo contiene cicli!")

    ctx, locks, q = {}, {n["name"]: asyncio.Lock() for n in nodes}, asyncio.Queue()
    ws = [asyncio.create_task(_worker(q, ctx, nodes_map, locks)) for _ in range(num_workers)]
    for gen in nx.topological_generations(G):
        for name in gen: await q.put(name)
        await q.join()
    for w in ws: w.cancel()
    return ctx

# ---------------------------------------------------------------------------
# DSL compatibility layer
# ---------------------------------------------------------------------------

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