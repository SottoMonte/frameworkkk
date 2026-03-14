import asyncio
import networkx as nx
import time
from typing import List, Dict, Any, Callable
import inspect
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
    deps = deps or []
    params = params or {}
    
    # Automatizziamo l'arg_map
    sig = inspect.signature(fn)
    param_names = list(sig.parameters.keys())
    
    # Crea la mappa: prende i nomi dei parametri della funzione 
    # e li associa nell'ordine alle dipendenze (deps)
    # Esempio: deps=['input_A'], fn(data) -> arg_map={'input_A': 'data'}
    arg_map = {}
    for i, dep_name in enumerate(deps):
        if i < len(param_names):
            arg_map[dep_name] = param_names[i]
    return {
        "name": name,
        "fn": fn,
        "deps": deps or [],
        "params": params or {},
        "arg_map": arg_map or {},
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
        # 1. Recupero del dato iniziale (già pulito dal worker)
        data = kwargs.get('kwargs')
        # 2. Esecuzione sequenziale
        for fn in fns:
            data = await fn(data) if asyncio.iscoroutinefunction(fn) else fn(data)
            
            # 3. Controllo errore logico (Ispezione)
            # Se la funzione ha restituito un oggetto che segnala un fallimento,
            # ci fermiamo e restituiamo l'errore al worker
            if isinstance(data, dict) and data.get("success") is False:
                return data 
                
        # Ritorno del risultato finale
        return data
        
    return node(name, node_fn, deps)

def foreach2(name, fn, data_dep):
    async def node_fn(**data):
        # Recupera la lista dalla dipendenza
        print("###################@",data)
        data_list = data.get('data', [])
        if data_list is None:
            return {"success": False, "errors": [f"Dati da {data_dep} sono None"]}
            
        results = []
        sig = inspect.signature(fn)
        param_name = list(sig.parameters.keys())[0] # Prende il nome del primo parametro (es. 'x')

        for item in data_list:
            # Passa l'item con il nome corretto alla funzione
            call_kwargs = {param_name: item}
            res = await fn(**call_kwargs) if asyncio.iscoroutinefunction(fn) else fn(**call_kwargs)
            
            if isinstance(res, dict) and res.get("success") is False:
                return res # Interrompi se c'è un errore logico
            results.append(res)
            
        return results
        
    # Importante: il foreach deve dichiarare data_dep come dipendenza
    return node(name, node_fn, deps=[data_dep])

def foreach(name, fn, data_dep=None):
    deps = [data_dep] if data_dep else []
    async def node_fn(**kwargs):
        data = kwargs.get('kwargs', [])
        outputs = []
        
        for item in data:
            # Eseguiamo la funzione. Se solleva un'eccezione, il worker la catturerà
            # rendendo il nodo interamente fallito (crash di sistema).
            res = await fn(item) if asyncio.iscoroutinefunction(fn) else fn(item)
            
            # Controllo se l'item specifico ha restituito un errore logico
            if isinstance(res, dict) and res.get("success") is False:
                # Possiamo scegliere: interrompere il foreach o loggare l'errore
                # Qui restituiamo un errore che spiega quale item ha fallito
                return {
                    "success": False, 
                    "errors": [f"Errore logico nell'item {item}: {res.get('message', 'Errore sconosciuto')}"],
                    "outputs": None
                }
            
            outputs.append(res)
            
        return outputs 
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
    while True:
        node_name = await queue.get()
        node = nodes_map[node_name]
        
        async with locks[node_name]:
            if node_name not in context:
                start = time.perf_counter()
                
                '''deps = node.get("deps", [])
                # Il worker estrae solo il valore 'outputs' (il dato puro)
                dep_results = {dep: context[dep]["outputs"] for dep in deps if dep in context}
                kwargs = {**node.get("params", {}), **dep_results}'''
                # --- INSERISCI IL CODICE QUI ---
                deps = node.get("deps", [])
                arg_map = node.get("arg_map", {})
                
                # Prepariamo i dati dalle dipendenze
                raw_dep_results = {dep: context[dep]["outputs"] for dep in deps if dep in context}
                
                # Inizializziamo con i parametri statici del nodo
                kwargs = {**node.get("params", {})}
                
                # Applichiamo la mappatura
                for dep_name, value in raw_dep_results.items():
                    target_name = arg_map.get(dep_name, dep_name)
                    kwargs[target_name] = value
                
                try:
                    fn = node["fn"]
                    res = await fn(**kwargs) if asyncio.iscoroutinefunction(fn) else fn(**kwargs)
                    
                    # LOGICA AGGIUNTA:
                    # Se la funzione di business ha restituito un dizionario con "success": False,
                    # lo trattiamo come un errore logico, non un crash di sistema.
                    if isinstance(res, dict) and "success" in res and res["success"] is False:
                        context[node_name] = res # Manteniamo la struttura di errore logico
                    else:
                        # Successo standard
                        context[node_name] = success(res, start_time=start)
                        
                except Exception as e:
                    # Crash di sistema (Eccezione Python)
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