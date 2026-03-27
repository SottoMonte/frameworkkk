"""DAG Engine v11 - deps_policy + reactive triggers"""

import asyncio, inspect, time
from typing import Any, Dict, Callable, List
import networkx as nx
import functools
import uuid

# ─────────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────────

def _res(ok, value=None, errors=None, t0=None):
    return {
        "action": None,
        "success": ok,
        "outputs": value if ok else None,
        "errors": errors if isinstance(errors, list) else ([str(errors)] if errors else []),
        "time": (time.perf_counter() - t0) if t0 else 0.0,
        "updated_at": time.time(), # Timestamp assoluto
        "version": str(uuid.uuid4())[:8], # ID univoco del run
        "duration": 0, # Durata del nodo
    }

def success(v, t0=None): return _res(True, v, None, t0)
def error(e, t0=None):   return _res(False, None, e, t0)
def output(v):           return v.get("outputs") if isinstance(v, dict) and v.get("success") is not None else v
def is_result(v):        return isinstance(v, dict) and v.get("success") is not None

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _set(ctx, path, val):
    parts = path.split(".")
    for p in parts[:-1]:
        ctx = ctx.setdefault(p, {})
    ctx[parts[-1]] = val

# ─────────────────────────────────────────────
# NODE DSL
# ─────────────────────────────────────────────

def node(name: str, fn: Callable, **kw):
    return {
        "name": name,
        "fn": fn,
        "deps": kw.get("deps", []),
        "policy": kw.get("policy", "all"),
        "meta": kw.get("meta", False),
        "trigger": kw.get("trigger"),
        "schedule":  kw.get("schedule"),
        "duration":  kw.get("duration"),
        "timeout": kw.get("timeout",30),
        "retries": kw.get("retries", 0),
        "retry_delay": kw.get("retry_delay", 0),
        "when": kw.get("when"),
        "path": kw.get("path", name),
        "cache": kw.get("cache", False),
        "on_start": kw.get("on_start"),
        "on_success": kw.get("on_success"),
        "on_error": kw.get("on_error"),
        "on_end": kw.get("on_end"),
    }

# ── DSL ───────────────────────────────────────────────────────────────────────

def step(fn, *a, **kw): return (fn, a, kw)

async def _call(fn, *a, **kw):
    if callable(fn):
        r = fn(*a, **kw)
        return await r if inspect.isawaitable(r) else r
    return fn

def action(custom_filename: str = __file__, app_context=None, **constants):
    def decorator(function):
        if asyncio.iscoroutinefunction(function):
            @functools.wraps(function)
            async def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = await function(*args, **kwargs)
                    return result|{"action": function.__name__, "time": start_time}
                except Exception as e:
                    return error(e, start_time)|{"action": function.__name__, "time": start_time}
            return wrapper
        else:
            @functools.wraps(function)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = function(*args, **kwargs)|{"action": function.__name__, "time": start_time}
                    return result|{"action": function.__name__, "time": start_time}
                except Exception as e:
                    return error(e, start_time)|{"action": function.__name__, "time": start_time}
            return wrapper
    return decorator

async def act(s):
    t0 = time.perf_counter()
    if not isinstance(s, tuple):
        return error("invalid step", t0)
    fn, args, kwargs = s
    try:
        r = await _call(fn, *args, **kwargs)
        return r if is_result(r) else success(r, t0)
    except Exception as e:
        return error(e, t0)

# ── EXTENSIONS ────────────────────────────────────────────────────────────────

async def branch(cond, ctx, branches):
    return branches[cond if isinstance(cond, bool) else cond(**ctx)]

def foreach(iterable, fn, args=()):
    async def _fn(view):
        items = view.get("items") or iterable
        return [await _call(fn, view, arg) for arg in args for _ in items]
    return _fn

@action()
async def pipeline(iterable, *functions):
    r = iterable
    print("\n #################### NODE_NAME:",iterable["node"]["name"])
    for fn in functions:
        r = await fn(r)
        print(r.get("errors"),r.get("action"))
        if not r["success"]: return error(r["errors"], r["time"])
        r = output(r)
    return success(r)

async def reset(old,new):
    return new

async def switch(data, cases):
    for cond, fn in cases.items():
        if cond is True: continue
        if callable(cond) and cond(**data) is True:
            return (await _call(fn, data))[0] if callable(fn) else fn
    default = cases.get(True)
    if default: return (await _call(default, data))[0] if callable(default) else default

# ─────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────

class DagRunner:

    def __init__(self, workers=3):
        self.workers = workers

        self.graphs = {}
        self.nodes = {}

        self.sessions = {}

        self.queue = asyncio.Queue()
        self.tasks = []
        self.running = False

        # 🔥 reactive index
        self.triggers = {}  # node_name -> [listeners]
        self.cancelled_sessions: set = set() 

    # ─────────────────────────────────────────
    # FILE
    # ─────────────────────────────────────────

    async def add_file(self, name: str, nodes: List[Dict]):
        G = nx.DiGraph()
        nm = {n["name"]: n for n in nodes}

        self.triggers[name] = {}

        for n in nodes:
            G.add_node(n["name"])

            # deps graph
            for d in n.get("deps", []):
                if d in nm:
                    G.add_edge(d, n["name"])

            # 🔥 trigger graph
            trg = n.get("trigger")
            if trg:
                self.triggers[name].setdefault(trg, []).append(n["name"])

        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("DAG con cicli")

        self.graphs[name] = G
        self.nodes[name] = nm

    # ─────────────────────────────────────────
    # SESSION
    # ─────────────────────────────────────────

    def create_session(self, sid: str, fname: str, ctx=None):
        ctx = dict(ctx or {})

        self.sessions[sid] = {
            "file": fname,
            "ctx": ctx,
            "results": {},
            "done": {n: asyncio.Event() for n in self.nodes[fname]},
            "schedulers": {}
        }

        for n in self.graphs[fname].nodes:
            if self.graphs[fname].in_degree(n) == 0:
                self.queue.put_nowait((sid, n))

    async def close_session(self, sid: str):
        """
        Rimuove la sessione e pulisce le risorse.
        """
        if sid not in self.sessions:
            return

        # 1. Marca come cancellata — i worker la ignoreranno
        session = self.sessions[sid]
        self.cancelled_sessions.add(sid)

        for task in session["schedulers"].values():
            task.cancel()

        # 2. Sblocca i wait_node pendenti
        for event in session["done"].values():
            if not event.is_set():
                event.set()

        # 3. Rimuovi i dati della sessione
        del self.sessions[sid]
        
        # 4. Pulisci il tombstone dopo un po'
        async def _cleanup_tombstone():
            await asyncio.sleep(60)
            self.cancelled_sessions.discard(sid)

        asyncio.create_task(_cleanup_tombstone())
        print(f"[Session {sid}] Cleaned up successfully.")

    async def clear_all_sessions(self):
        """Rimuove tutte le sessioni attive."""
        sids = list(self.sessions.keys())
        for sid in sids:
            await self.close_session(sid)

    # ─────────────────────────────────────────
    # WORKERS
    # ─────────────────────────────────────────

    async def start(self):
        self.running = True
        self.tasks = [asyncio.create_task(self._worker()) for _ in range(self.workers)]

    async def stop(self):
        self.running = False
        for t in self.tasks:
            t.cancel()

    async def _worker(self):
        while self.running:
            try:
                sid, name = await asyncio.wait_for(self.queue.get(), 0.2)
            except asyncio.TimeoutError:
                continue

            # scarta silenziosamente i task di sessioni chiuse
            if sid in self.cancelled_sessions:
                self.queue.task_done()
                continue
            await self._run_node(sid, name)
            self.queue.task_done()

    # ─────────────────────────────────────────
    # CORE
    # ─────────────────────────────────────────

    async def _run_node(self, sid: str, name: str):
        session = self.sessions[sid]
        nd = self.nodes[session["file"]][name]

        # Inizializziamo il pacchetto dati che viaggerà nella pipeline
        d = {
            "sid": sid,
            "node": nd,
            "ctx": session["ctx"],
            "results": session["results"],
            "result": None,
            "t0": time.perf_counter()
        }

        # 1. Verifica dipendenze e policy
        steps = [self._check_deps]

        # 2. Controllo Quota Tempo (Storico)
        if nd.get("duration"):    steps.append(self._handle_duration)
        # 3. Verifica pre-condizioni logiche
        if nd.get("when"):        steps.append(self._check_when)
        # 4. Hook d'inizio
        if nd.get("on_start"): steps.append(functools.partial(self._run_hook, hook_name="on_start"))
        # 5. Esecuzione (con retry interno)
        steps.append(self._execute_step)
        # 6. Hook di fine (successo/errore)
        if nd.get("on_success"): steps.append(functools.partial(self._run_hook, hook_name="on_success"))
        if nd.get("on_error"): steps.append(functools.partial(self._run_hook, hook_name="on_error"))
        # 7. Hook di fine
        if nd.get("on_end"): steps.append(functools.partial(self._run_hook, hook_name="on_end"))
        # 8. Scrittura risultati nel contesto
        steps.append(self._save_step)
        # 9. Trigger successori
        steps.append(self._dispatch)

        # Esecuzione a tappe
        await pipeline(d, *steps)

        session["done"][name].set()

    # ─────────────────────────────────────────
    # OPS
    # ─────────────────────────────────────────

    @action()
    async def _check_deps(self, d):
        sid      = d["sid"]
        deps     = d["node"].get("deps", [])
        node_name = d["node"]["name"]
        policy   = d["node"].get("policy", "all")
        res      = d["results"]
        session  = self.sessions[sid]
        use_cache = d["node"].get("cache", False)
        # 1. Se non ci sono dipendenze, via liberi
        if not deps:
            return success(d)

        # 1. Check di Sincronizzazione (Eventi)
        not_ready = [dep for dep in deps if dep in session["done"] and not session["done"][dep].is_set()]

        if not_ready and not use_cache:
            # Se i padri non sono pronti, rilasciamo il worker!
            # Aspettiamo un pochino e rimettiamo il nodo in coda.
            async def _retry_later():
                print(f"[Session {sid}] Waiting for deps: {not_ready}")
                await asyncio.sleep(0.5) # Piccolo delay per non floodare la coda
                self.queue.put_nowait((sid, node_name))
            
            asyncio.create_task(_retry_later())
            
            # Interrompiamo la pipeline corrente con un errore "silenzioso" 
            # o uno stato che fermi l'esecuzione attuale senza loggare disastri.
            return error(f"Waiting for deps: {not_ready}")

        # 2. Check di Freschezza (Timestamp/Version)
        # Se il figlio è schedulato, non vogliamo che giri 100 volte sullo stesso dato del padre
        if not use_cache:
            my_last_run_time = res.get(node_name, {}).get("updated_at", 0)
            
            # Controlliamo se almeno un padre ha un dato più nuovo della nostra ultima esecuzione
            fresh_data = False
            for dep in deps:
                if dep in res:
                    if res[dep]["updated_at"] > my_last_run_time:
                        fresh_data = True
                        break
            
            # Se siamo già stati eseguiti una volta e nessun padre ha dati nuovi...
            if node_name in res and not fresh_data:
                # Rimettiamo in coda silenziosamente (aspettando il prossimo battito del padre)
                async def _wait_for_fresh():
                    await asyncio.sleep(0.5)
                    self.queue.put_nowait((sid, node_name))
                asyncio.create_task(_wait_for_fresh())
                return error("No fresh data from parents yet.")

        completed = [dep for dep in deps if dep in res]
        succeeded = [dep for dep in completed if res[dep]["success"]]

        if policy == "all":
            if len(succeeded) == len(deps):
                return success(d)
            failed = [dep for dep in completed if not res[dep]["success"]]
            return error(f"policy=all failed: {failed}")

        if policy == "any":
            if len(succeeded) >= 1:
                return success(d)
            return error("policy=any failed")

        if isinstance(policy, int):
            if len(succeeded) >= policy:
                return success(d)
            return error(f"policy={policy} >= ({len(succeeded)} succeeded)")

        return error(f"unknown policy: {policy!r}")

    @action()
    async def _check_when(self, d):
        fn = d["node"].get("when")
        if not fn:
            return success(d)
        #print(fn(d["ctx"] | d["results"]))
        if bool(fn(d["ctx"] | d["results"])):
            return success(d)
        return error("Invalid when")

    @action()
    async def _execute_step(self, d):
        nd, ctx, res = d["node"], d["ctx"], d["results"]
        retries = nd.get("retries", 0)
        delay = nd.get("retry_delay", 0)
        
        # Prepariamo gli input: ctx globale + risultati dei nodi dipendenti
        #inputs = ctx | {k: v["outputs"] for k, v in res.items()}
        if nd.get("meta"):
            # Passa l'intero oggetto Result per ogni dipendenza
            inputs = ctx | {k: v for k, v in res.items()}
        else:
            # Comportamento standard: passa solo il valore prodotto
            inputs = ctx | {k: v["outputs"] for k, v in res.items()}
        
        last_result = None
        for i in range(retries + 1):
            try:
                # Esecuzione della funzione core
                r = await _call(nd["fn"], inputs)
                last_result = r if is_result(r) else success(r, d["t0"])
                if last_result["success"]:
                    break
            except Exception as e:
                last_result = error(e, d["t0"])
            
            if i < retries:
                await asyncio.sleep(delay)
        
        d["result"] = last_result
        return success(d)

    @action()
    async def _run_hook(self, d, hook_name: str):
        nd = d["node"]
        hook_val = nd.get(hook_name)
        sid = d["sid"]
        
        if not hook_val:
            return success(d)

        try:
            # GESTIONE STRINGA O LISTA DI STRINGHE (TRIGGER REATTIVI)
            if isinstance(hook_val, (str, list)):
                # Normalizziamo in una lista per iterare
                targets = [hook_val] if isinstance(hook_val, str) else hook_val
                
                for target_node in targets:
                    if target_node in self.sessions[sid]["done"]:
                        # Reset dell'evento: permette al nodo di essere eseguito di nuovo
                        self.sessions[sid]["done"][target_node].clear()
                        print(f"🔄 [Hook {hook_name}] Reset & Trigger: '{target_node}'")
                    else:
                        print(f"🚀 [Hook {hook_name}] First Trigger: '{target_node}'")
                    
                    # Mettiamo il nodo in coda per i worker
                    self.queue.put_nowait((sid, target_node))

            # GESTIONE FUNZIONE (LOGICA CUSTOM)
            elif callable(hook_val):
                await _call(hook_val, d, d.get("result"))
                
            return success(d)
        except Exception as e:
            print(f"❌ Errore nell'hook {hook_name} di {nd['name']}: {e}")
            return success(d)

    @action()
    async def _handle_duration(self, d):
        nd = d["node"]
        max_dur = nd.get("duration")
        if not max_dur: return success(d)

        # Recuperiamo quanto tempo ha accumulato il nodo finora nella sessione
        current_total = d["results"].get(nd["name"], {}).get("duration", 0.0)

        if current_total >= max_dur:
            return error(f"Quota temporale esaurita ({current_total:.2f}s >= {max_dur}s)")
        
        return success(d)

    @action()
    async def _save_step(self, d):
        nd, result = d["node"], d["result"]
        sid = d["sid"]
        session = self.sessions[sid]
        
        # Salvataggio standard
        _set(d["ctx"], nd.get("path"), result["outputs"])
        session["results"][nd["name"]] = result
        
        # Registriamo che questo nodo ha appena prodotto questa versione
        session.setdefault("last_seen", {})[nd["name"]] = result["version"]

        result["duration"] += result["time"]
        
        return success(d)

    @action()
    async def _dispatch(self, d):
        sid = d["sid"]
        node_name = d["node"]["name"]
        session = self.sessions[sid]
        interval = d["node"].get("schedule")
        
        # 1. Trigger e Reset Successori
        for nxt in self.graphs[session["file"]].successors(node_name):
            nxt_node = self.nodes[session["file"]][nxt]
            
            # Se il FIGLIO vuole dati freschi (cache=False), resettiamo il suo 'done'
            if not nxt_node.get("cache") and nxt in session["done"]:
                session["done"][nxt].clear()
            
            self.queue.put_nowait((sid, nxt))

        # 2. Reactive triggers
        for trg in self.triggers[session["file"]].get(node_name, []):
            self.queue.put_nowait((sid, trg))

        # 2. AUTO-SCHEDULAZIONE PERSISTENTE
        if interval and node_name not in session["schedulers"]:
            
            async def _heartbeat():
                try:
                    while sid in self.sessions and sid not in self.cancelled_sessions:
                        await asyncio.sleep(interval)
                        
                        # Reset dell'evento per permettere una nuova esecuzione pulita
                        if node_name in session["done"]:
                            session["done"][node_name].clear()
                        
                        # Rimettiamo il nodo in coda per i worker
                        self.queue.put_nowait((sid, node_name))
                        
                        # Opzionale: attendiamo che il nodo finisca prima di far ripartire il timer 
                        # (per evitare accumuli se l'esecuzione dura più dell'intervallo)
                        await session["done"][node_name].wait()
                        
                except asyncio.CancelledError:
                    pass
            # Crea il task UNA SOLA VOLTA per tutta la durata della sessione
            session["schedulers"][node_name] = asyncio.create_task(_heartbeat())

        return success(d)

    # ─────────────────────────────────────────
    # REACTIVE API
    # ─────────────────────────────────────────

    def emit(self, sid: str, name: str, value: Any = None):
        """Trigger manuale (event sourcing light)"""
        session = self.sessions[sid]

        if value is not None:
            _set(session["ctx"], name, value)

        self.queue.put_nowait((sid, name))

    # ─────────────────────────────────────────
    # HOOKS
    # ─────────────────────────────────────────

    async def _hook(self, fn, d, result=None):
        if not fn:
            return
        try:
            await _call(fn, d, result)
        except:
            pass

    async def wait_node(self, sid, name):
        await self.sessions[sid]["done"][name].wait()