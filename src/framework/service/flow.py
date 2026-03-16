import asyncio, inspect, time
import networkx as nx
from typing import Any, Callable, List, Dict

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
errors_of = lambda v: v["errors"]  if is_result(v) else []
_elapsed  = lambda t0: (time.perf_counter() - t0) if t0 else None

ok = success; fail = error; output = value_of

# ── Nodo DAG ──────────────────────────────────────────────────────────────────

def node(name: str, fn: Callable, deps: List[str] = None, params: dict = None,
         schedule: float = None, event_trigger: Callable = None):
    return {"name": name, "fn": fn, "deps": deps or [], "params": params or {},
            "schedule": schedule, "event_trigger": event_trigger}

# ── Helpers nested context ────────────────────────────────────────────────────

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

# ── Runtime ───────────────────────────────────────────────────────────────────

async def _run_node(n, env, ctx, locks):
    t0   = time.perf_counter()
    name = n["name"]
    failed = [d for d in n["deps"] if is_result(ctx.get(d)) and not ctx[d]["success"]]
    if failed:
        ctx[name] = error(f"dep failed: {', '.join(failed)}", t0); return
    try:
        r      = await n["fn"](env)
        result = r if is_result(r) else success(r, t0)
        ctx[name] = result
        _set_nested(env, name, value_of(result))
    except Exception as e:
        ctx[name] = error(e, t0)

async def _worker(q, env, ctx, nodes_map, locks):
    while True:
        name = await q.get()
        async with locks[name]:
            if name not in ctx:
                await _run_node(nodes_map[name], env, ctx, locks)
        q.task_done()

async def run(nodes: List[Dict[str, Any]], env: dict = None, num_workers=3):
    G, nodes_map = nx.DiGraph(), {n["name"]: n for n in nodes}
    for n in nodes:
        G.add_node(n["name"])
        for d in n["deps"]: G.add_edge(d, n["name"])
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Il grafo contiene cicli!")
    shared_env = dict(env or {})
    ctx        = {}
    locks      = {n["name"]: asyncio.Lock() for n in nodes}
    q          = asyncio.Queue()
    ws = [asyncio.create_task(_worker(q, shared_env, ctx, nodes_map, locks))
          for _ in range(num_workers)]
    for gen in nx.topological_generations(G):
        for name in gen: await q.put(name)
        await q.join()
    for w in ws: w.cancel()
    return shared_env

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