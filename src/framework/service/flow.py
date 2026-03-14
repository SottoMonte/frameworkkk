import asyncio
import networkx as nx
import time
from typing import List, Dict, Any, Callable

# ------------------ Funzioni di supporto ------------------

def success(outputs, start_time=None):
    return {
        "success": True,
        "outputs": outputs,
        "errors": [],
        "time": (time.perf_counter() - start_time) if start_time else None
    }

def error(err, start_time=None):
    return {
        "success": False,
        "outputs": None,
        "errors": [str(err)] if not isinstance(err, list) else err,
        "time": (time.perf_counter() - start_time) if start_time else None
    }

def output(value):
    """Normalizza l'output di un nodo, coerente con success/error"""
    if isinstance(value, dict) and "outputs" in value and "errors" in value:
        return value.get("outputs")
    else:
        return value

# ------------------ Nodo DAG ------------------

def node(
    name: str,
    fn: Callable,
    deps: List[str] = None,
    params: dict = None,
    schedule: float = None,        # seconds
    event_trigger: Callable = None # funzione che restituisce booleano
):
    """Crea un nodo DAG come dizionario"""
    return {
        "name": name,
        "fn": fn,
        "deps": deps or [],
        "params": params or {},
        "schedule": schedule,
        "event_trigger": event_trigger
    }

# ------------------ Nodo wrapper come nodo ------------------

def retry(fn_node, retries=3, delay=1):
    async def node_fn(**kwargs):
        for i in range(retries):
            try:
                return await fn_node["fn"](**kwargs) if asyncio.iscoroutinefunction(fn_node["fn"]) else fn_node["fn"](**kwargs)
            except Exception as e:
                if i == retries-1:
                    raise
                await asyncio.sleep(delay)
    return node(f"retry({fn_node['name']})", node_fn, deps=fn_node["deps"])

def timeout(fn_node, seconds=5):
    async def node_fn(**kwargs):
        return await asyncio.wait_for(fn_node["fn"](**kwargs) if asyncio.iscoroutinefunction(fn_node["fn"]) else fn_node["fn"](**kwargs), timeout=seconds)
    return node(f"timeout({fn_node['name']})", node_fn, deps=fn_node["deps"])

def catch(fn_node, recovery_fn=lambda x=None: None):
    async def node_fn(**kwargs):
        try:
            return await fn_node["fn"](**kwargs) if asyncio.iscoroutinefunction(fn_node["fn"]) else fn_node["fn"](**kwargs)
        except Exception:
            return await recovery_fn(**kwargs) if asyncio.iscoroutinefunction(recovery_fn) else recovery_fn(**kwargs)
    return node(f"catch({fn_node['name']})", node_fn, deps=fn_node["deps"])

# ------------------ Costrutti avanzati come nodi ------------------

def pipeline(name, fns: List[Callable], deps=None):
    deps = deps or []
    async def node_fn(**kwargs):
        print("@@@@@@@@@@@@", kwargs)
        # Prendiamo solo il primo risultato della prima dipendenza
        # assicurandoci di estrarre il valore pulito
        first_dep = deps[0]
        last = kwargs.get(first_dep)
        
        # Se last è già il risultato normalizzato, usalo, altrimenti estrai
        data = output(last)
        
        for fn in fns:
            data = await fn(data) if asyncio.iscoroutinefunction(fn) else fn(data)
            data = output(data)
        return data
    return node(name, node_fn, deps)

def foreach(name, fn, data_dep=None):
    deps = [data_dep] if data_dep else []
    async def node_fn(**kwargs):
        print("@@@@@@@@@@@@", kwargs)
        data = kwargs.get(data_dep) if data_dep else []
        outputs, errors = [], []
        for item in data:
            try:
                res = await fn(item) if asyncio.iscoroutinefunction(fn) else fn(item)
                outputs.append(res)
            except Exception as e:
                outputs.append(None)
                errors.append(str(e))
        return output({"outputs": outputs, "errors": errors, "success": len(errors) == 0})
    return node(name, node_fn, deps)

def switch(name, cases: List, deps=None):
    deps = deps or []
    async def node_fn(**kwargs):
        for cond, act in cases:
            check = cond(**kwargs) if callable(cond) else cond
            if check:
                return await act(**kwargs) if asyncio.iscoroutinefunction(act) else act(**kwargs)
        return None
    return node(name, node_fn, deps)

# ------------------ Motore di Esecuzione ------------------

async def worker(queue: asyncio.Queue, context: Dict, nodes_map: Dict, locks: Dict):
    """Worker che esegue i nodi prelevati dalla coda."""
    while True:
        node_name = await queue.get()
        node = nodes_map[node_name]
        
        async with locks[node_name]:
            # Controllo di memorizzazione
            if node_name not in context:
                start = time.perf_counter()
                
                # Risoluzione dipendenze dal context
                deps = node.get("deps", [])
                dep_results = {dep: context[dep]["outputs"] for dep in deps if dep in context}
                kwargs = {**node.get("params", {}), **dep_results}
                
                try:
                    fn = node["fn"]
                    res = await fn(**kwargs) if asyncio.iscoroutinefunction(fn) else fn(**kwargs)
                    context[node_name] = success(res, start_time=start)
                except Exception as e:
                    context[node_name] = error(e, start_time=start)
        
        queue.task_done()

async def run(nodes: List[Dict[str, Any]], num_workers: int = 3):
    # 1. Analisi del Grafo con NetworkX
    G = nx.DiGraph()
    nodes_map = {n["name"]: n for n in nodes}
    for n in nodes:
        G.add_node(n["name"])
        for dep in n.get("deps", []):
            G.add_edge(dep, n["name"])
            
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("Errore: Il grafo contiene cicli!")

    context = {}
    locks = {n["name"]: asyncio.Lock() for n in nodes}
    queue = asyncio.Queue()
    
    # 2. Avvio del pool di Worker
    workers = [asyncio.create_task(worker(queue, context, nodes_map, locks)) 
               for _ in range(num_workers)]
    
    # 
    
    # 3. Esecuzione per Generazioni (Livelli)
    # NetworkX garantisce che i nodi in 'generation' abbiano le dipendenze soddisfatte
    for generation in nx.topological_generations(G):
        for node_name in generation:
            await queue.put(node_name)
        await queue.join() 
        
    # 
    
    # Pulizia
    for w in workers: w.cancel()
    return context