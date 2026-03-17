# 🚀 FLOW.PY - Documentazione Completa

## 📋 Indice
1. [Panoramica](#panoramica)
2. [Installazione](#installazione)
3. [Features](#features)
4. [API Reference](#api-reference)
5. [Esempi](#esempi)
6. [Best Practices](#best-practices)

---

## 📌 Panoramica

**flow.py** è un framework completo per la creazione e l'esecuzione di DAG (Directed Acyclic Graphs) in Python con supporto per:

- ✅ **Esecuzione parallela** con asyncio
- ✅ **Monitoraggio completo** di tutti gli eventi
- ✅ **Retry automatico** con backoff esponenziale
- ✅ **Caching intelligente** dei risultati
- ✅ **Event triggers** per workflow reattivi
- ✅ **Dipendenze** tra nodi
- ✅ **Scheduling** periodico

### Architettura

```
┌─────────────────────────────────────────┐
│         DAG Definition (nodes)          │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   Topological Sort (NetworkX)    │  │
│  └──────────────────────────────────┘  │
│           ↓                             │
│  ┌──────────────────────────────────┐  │
│  │  Async Queue + Worker Pool       │  │
│  └──────────────────────────────────┘  │
│           ↓                             │
│  ┌──────────────────────────────────┐  │
│  │  Retry Logic (w/ Backoff)        │  │
│  ├──────────────────────────────────┤  │
│  │  Cache (w/ TTL)                  │  │
│  ├──────────────────────────────────┤  │
│  │  Event Triggers                  │  │
│  ├──────────────────────────────────┤  │
│  │  Monitoring & Metrics            │  │
│  └──────────────────────────────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

---

## 💻 Installazione

```python
from flow import node, run, success, error, RetryConfig
```

---

## ✨ Features

### 1. MONITORAGGIO (`DagMonitor`)

Traccia **ogni evento** durante l'esecuzione:

```python
from flow import node, run

async def my_task(env):
    return success("done")

nodes = [node("task", my_task)]

env, ctx, monitor = await run(nodes, enable_monitoring=True)

# Accedi ai dati
report = monitor.get_report()
print(report['total_duration'])  # Tempo totale
print(report['metrics'])         # Metriche per nodo
print(report['events_summary'])  # Riepilogo eventi

# Stampa report formattato
monitor.print_report()
```

**Metriche Raccolte:**
- ✅ Durata di esecuzione (per esecuzione e aggregata)
- ✅ Numero di esecuzioni
- ✅ Successi vs Fallimenti
- ✅ Timeline di tutti gli eventi
- ✅ Min/Max/Avg timing

---

### 2. CACHING (`DagCache`)

Evita riesecuzioni inutili con cache con TTL:

```python
async def expensive_operation(env):
    # Questo verrà cachato
    await asyncio.sleep(5)
    return success("result")

nodes = [
    node("expensive", expensive_operation, 
          cache=True,           # Abilita cache
          cache_ttl=3600)       # TTL 1 ora
]

env, ctx, monitor = await run(nodes, enable_caching=True)
```

**Come Funziona:**
1. Prima esecuzione → esegui e salva in cache
2. Successive esecuzioni (entro TTL) → leggi dal cache
3. Dopo TTL → ripete il ciclo

**Caso d'Uso:**
```python
# Fetch di dati costosi
node("fetch_users", fetch_users, cache=True, cache_ttl=3600)
# Primo run: fetch dal DB
# Run successivi (entro 1h): leggi da cache
```

---

### 3. RETRY AUTOMATICO (`RetryConfig`)

Retry automatico con backoff esponenziale:

```python
from flow import RetryConfig

retry_config = RetryConfig(
    max_retries=3,              # Massimo 3 tentativi
    backoff=0.5,                # Delay iniziale 0.5s
    backoff_multiplier=2.0,     # Raddoppia ogni volta
    max_backoff=60.0            # Max delay 60s
)

async def flaky_operation(env):
    # Fallisc con errori temporanei
    if random.random() < 0.3:
        raise ConnectionError("Temporary network error")
    return success("done")

nodes = [
    node("flaky", flaky_operation, retry=retry_config)
]

env, ctx = await run(nodes)
```

**Backoff Esponenziale:**
```
Tentativo 1: fallisce → aspetta 0.5s
Tentativo 2: fallisce → aspetta 1.0s
Tentativo 3: fallisce → aspetta 2.0s
Tentativo 4: successo! ✅
```

**Output:**
```
⚠️  flaky fallito (tentativo 1/4), riprovando tra 0.5s...
⚠️  flaky fallito (tentativo 2/4), riprovando tra 1.0s...
⚠️  flaky fallito (tentativo 3/4), riprovando tra 2.0s...
✅ Successo al tentativo 4!
```

---

### 4. EVENT TRIGGERS

Un nodo può triggerare altri nodi:

```python
async def detector(env):
    return success("anomaly_found")

async def alert(env):
    return success("alert_sent")

async def logger(env):
    return success("logged")

nodes = [
    node("detector", detector, triggers=["alert", "logger"]),
    node("alert", alert),
    node("logger", logger),
]

env, ctx = await run(nodes)
# detector esegue → triggera alert e logger
```

---

## 📚 API Reference

### `node()`

```python
node(
    name: str,                          # Nome univoco
    fn: Callable,                       # Funzione da eseguire
    deps: List[str] = None,             # Dipendenze
    params: dict = None,                # Parametri
    schedule: float = None,             # Intervallo repetizione
    duration: float = None,             # Durata totale (con schedule)
    on_success: Callable = None,        # Callback su successo
    on_error: Callable = None,          # Callback su errore
    on_start: Callable = None,          # Callback su inizio
    triggers: List[str] = None,         # Nodi da triggerare
    retry: RetryConfig = None,          # Configurazione retry
    cache: bool = False,                # Abilita caching
    cache_ttl: float = 3600,            # TTL cache
) -> dict
```

### `run()`

```python
env, ctx, monitor = await run(
    nodes: List[Dict],                  # Nodi da eseguire
    env: dict = None,                   # Environment iniziale
    num_workers: int = 3,               # Worker paralleli
    enable_monitoring: bool = True,     # Abilita monitoring
    enable_caching: bool = True,        # Abilita caching
    cache_ttl: float = 3600,            # TTL cache globale
)

# Ritorna:
# - env: environment finale
# - ctx: risultati di ogni nodo
# - monitor: dati di monitoraggio (se abilitato)
```

### `RetryConfig`

```python
RetryConfig(
    max_retries: int = 3,               # Massimi tentativi
    backoff: float = 1.0,               # Delay iniziale
    backoff_multiplier: float = 2.0,    # Moltiplicatore
    max_backoff: float = 60.0,          # Delay massimo
)
```

### `DagMonitor`

```python
monitor.get_report()          # Dict con tutte le metriche
monitor.print_report()        # Stampa report formattato
monitor.log_event(...)        # Registra evento custom
monitor.record_execution(...) # Registra esecuzione nodo
```

---

## 💡 Esempi

### Esempio 1: Data Pipeline con Caching

```python
async def fetch_data(env):
    print("Fetching from API...")
    await asyncio.sleep(2)  # Simulazione API call
    return success({"users": [1, 2, 3]})

async def process_data(env):
    data = env.get("fetch")
    print(f"Processing {len(data['users'])} users")
    return success({"processed": len(data['users'])})

async def save_data(env):
    result = env.get("process")
    print(f"Saving {result['processed']} records")
    return success("saved")

nodes = [
    node("fetch", fetch_data, cache=True, cache_ttl=300),
    node("process", process_data, deps=["fetch"]),
    node("save", save_data, deps=["process"]),
]

# Prima esecuzione: 2s (fetch) + tempo processing/saving
env, ctx, monitor = await run(nodes)

# Seconda esecuzione: ~0s (cache hit) + tempo processing/saving
env, ctx, monitor = await run(nodes)
```

---

### Esempio 2: Retry con Fallbacks

```python
async def unstable_api(env):
    if random.random() < 0.5:
        raise ConnectionError("API down")
    return success({"status": "ok"})

async def fallback(env):
    return success({"status": "cached"})

nodes = [
    node("api", unstable_api, 
          retry=RetryConfig(max_retries=3, backoff=0.5)),
    node("fallback", fallback, deps=["api"]),
]

env, ctx = await run(nodes)
# Se API riesca: usa API response
# Se API fallisce (anche dopo retry): usa fallback
```

---

### Esempio 3: Monitoring in Real-Time

```python
env, ctx, monitor = await run(nodes, enable_monitoring=True)

report = monitor.get_report()

print(f"Pipeline took {report['total_duration']:.2f}s")
print(f"Events: {report['events_summary']}")

for node_name, metrics in report['metrics'].items():
    success_rate = (metrics['successes'] / metrics['executions'] * 100)
    avg_time = metrics['total_time'] / metrics['executions']
    print(f"{node_name}: {success_rate:.0f}% success, {avg_time:.3f}s avg")
```

---

### Esempio 4: Reactive Workflow con Triggers

```python
async def detector(env):
    # Detecta condizioni
    anomaly = env.get("check_metrics", False)
    if anomaly:
        return success("anomaly_detected")
    return success("all_good")

async def send_alert(env):
    return success("alert_sent_to_slack")

async def create_incident(env):
    return success("incident_created_in_jira")

async def log_event(env):
    return success("event_logged")

nodes = [
    node("detector", detector, 
          triggers=["alert", "incident", "logger"],
          schedule=60,           # Controlla ogni 60s
          duration=3600),        # Per 1 ora
    node("alert", send_alert),
    node("incident", create_incident),
    node("logger", log_event),
]

env = {"check_metrics": check_metrics_fn}
env, ctx, monitor = await run(nodes)

monitor.print_report()
```

---

## 🎯 Best Practices

### ✅ DO:

```python
# ✅ Usa cache per operazioni costose
node("expensive", expensive_fn, cache=True, cache_ttl=300)

# ✅ Usa retry per operazioni instabili
node("api", api_call, retry=RetryConfig(max_retries=3))

# ✅ Abilita monitoring in produzione
env, ctx, monitor = await run(nodes, enable_monitoring=True)

# ✅ Usa callbacks per side effects
def on_success(name, result, env):
    logger.info(f"{name} completed: {result}")

node("task", task_fn, on_success=on_success)

# ✅ Usa triggers per pipeline reattive
node("detector", detect, triggers=["alert", "log"])
```

### ❌ DON'T:

```python
# ❌ Non usare blocking operations nei nodi
async def bad(env):
    time.sleep(10)  # ⚠️ Blocca il worker!
    return success()

# ❌ Non cachare risultati volatili senza motivo
node("random", random_fn, cache=True)  # Inutile!

# ❌ Non ignorare gli errori nei callback
def bad_callback(name, result, env):
    raise Exception("oops")  # ⚠️ Potrebbe bloccare il DAG

# ❌ Non creare cicli di dipendenze
nodes = [
    node("A", fn, deps=["B"]),
    node("B", fn, deps=["A"]),  # ⚠️ Ciclo!
]
```

---

## 📊 Interpretazione del Report

```
📊 MONITORING REPORT
═══════════════════════════════════════════

Total Duration: 0.15s                     ← Tempo totale esecuzione
Total Events: 16                          ← Numero di eventi registrati

Event Summary: {                          ← Riepilogo per tipo
    'queued': 4,                          ← Nodi messi in coda
    'start': 5,                           ← Nodi iniziati
    'error': 1,                           ← Errori riscontrati
    'success': 4,                         ← Esecuzioni riuscite
    'trigger': 2                          ← Trigger attivati
}

Node Metrics:
  fetch:
    Executions: 1                         ← 1 esecuzione totale
    Successes: 1                          ← 1 riuscita
    Failures: 0                           ← 0 fallimenti
    Avg Time: 0.051s                      ← Tempo medio
    Min/Max: 0.051s / 0.051s              ← Range di tempo
```

---

## 🔗 Integrazione con Sistemi Esterni

### Database

```python
async def save_to_db(name, result, env):
    db = env.get("db")
    await db.insert("results", {
        "node": name,
        "result": result["outputs"],
        "timestamp": time.time()
    })

node("task", task_fn, on_success=save_to_db)
```

### Logging

```python
import logging

async def log_everything(name, result, env):
    logging.info(f"{name} completed: {result['outputs']}")

node("task", task_fn, on_success=log_everything)
```

### Monitoring (Prometheus, DataDog, etc.)

```python
async def send_metrics(name, result, env):
    metrics = env.get("metrics_client")
    metrics.gauge("dag.node.duration", result["time"])
    metrics.counter("dag.node.executions", 1)

node("task", task_fn, on_success=send_metrics)
```

---

## 🎓 Conclusione

**flow.py** è un framework production-ready per:
- 🔄 Pipeline di dati complesse
- 🚀 Workflow asincrone
- 🔬 Microservices orchestration
- 📊 ETL pipelines
- 🤖 ML workflows
- 📡 Event-driven architectures

Scegli flow.py per la tua prossima pipeline! 🚀