# DSL Reference Guide

## Overview
Il DSL del framework è un linguaggio dichiarativo per orchestrare servizi, gestire flussi di dati e definire l'architettura dell'applicazione.

## Sintassi Base

### Variabili
```dsl
nome : valore;
numero : 42;
testo : "Hello World";
```

### Dizionari
```dsl
config : {
    "host": "localhost";
    "port": 8080;
};
```

### Tuple/Liste
```dsl
ports : ("presentation", "persistence", "message");
```

### Pipe Operator
```dsl
risultato : input | funzione1 | funzione2;
```

## Funzioni Built-in

### 1. Modularità

#### `include(path)`
Carica e merge variabili da un altro file DSL.
```dsl
include("constants.dsl");
# Ora puoi usare le variabili definite in constants.dsl
```

### 2. Controllo di Flusso

#### `match(cases)` / `switch(cases)`
Branching condizionale. Supporta sia sintassi con pipe che chiamata diretta.
```dsl
# Con pipe
result : value | match({
    "@ == 'A'": action_a;
    "@ == 'B'": action_b;
    "true": default_action;
});

# Chiamata diretta
result : match(cases_dict, value);
```

#### `branch(on_success, on_failure)`
Instrada basandosi sul campo 'success' del risultato.
```dsl
result : operation | branch(
    success_handler,
    error_handler
);
```

### 3. Orchestrazione Parallela

#### `parallel(action)` / `batch(action)`
Esegue azioni in parallelo su una collezione.
```dsl
results : items | parallel(process);
```

#### `race(*steps)`
Esegue più step in parallelo, ritorna il primo che completa.
```dsl
fastest : race(step1, step2, step3);
```

#### `all_completed(tasks)`
Attende il completamento di tutti i task (via executor).
```dsl
results : all_completed(task_list);
```

#### `first_completed(operations)`
Ritorna il primo task che completa con successo (via executor).
```dsl
winner : first_completed(operations);
```

### 4. Orchestrazione Sequenziale

#### `chain(tasks)` / `sequential(tasks)`
Esegue task in sequenza (via executor).
```dsl
results : chain(task_list);
```

#### `foreach(action)`
Applica un'azione a ogni elemento di una collezione.
```dsl
processed : items | foreach(register);
```

### 5. Gestione Errori

#### `catch(try_step, catch_step)`
Esegue try_step, se fallisce esegue catch_step.
```dsl
result : risky_operation | catch(fallback_operation);
```

#### `retry(action_step, attempts, delay)`
Riprova un'operazione in caso di fallimento.
```dsl
result : unstable_api | retry(attempts=3, delay=1.0);
```

#### `fallback(primary, secondary)`
Esegue primary, se fallisce esegue secondary.
```dsl
result : fallback(primary_service, backup_service);
```

### 6. Controllo Temporale

#### `timeout(action_step, max_seconds)`
Annulla l'operazione se supera il tempo limite.
```dsl
result : slow_operation | timeout(max_seconds=30);
```

#### `throttle(action_step, rate_limit_ms)`
Limita la frequenza di esecuzione.
```dsl
result : api_call | throttle(rate_limit_ms=1000);
```

### 7. Manipolazione Dati

#### `transform(template)`
Trasforma dati usando un template con interpolazione.
```dsl
users : raw_data | transform({
    "id": "@.user_id";
    "name": "@.first_name" + " " + "@.last_name";
    "email": "@.contact.email";
});
```

#### `filter(keys)`
Filtra un dizionario mantenendo solo le chiavi specificate.
```dsl
active_ports : all_ports | filter(("message", "persistence"));
```

#### `pick(keys)`
Alias di filter.

#### `map(mistql_query)`
Applica una query MistQL a ogni elemento.
```dsl
ids : users | map("id");
```

#### `keys` / `values` / `items`
Estrae chiavi, valori o coppie chiave-valore da un dizionario.
```dsl
port_names : config | keys;
port_values : config | values;
port_pairs : config | items;
```

### 8. Conversione e Formattazione

#### `convert(target_type, output_format, input_format)`
Converte tra formati (json, toml, yaml, dict, str).
```dsl
config : "config.toml" | resource | convert(dict, "toml");
```

#### `format(target)`
Formatta una stringa o risorsa.
```dsl
content : template | format;
```

#### `get(path, default)`
Accede a valori nested usando dot notation.
```dsl
host : config | get("database.host", "localhost");
```

### 9. I/O e Risorse

#### `resource(path)`
Carica una risorsa (file, modulo Python, ecc.).
```dsl
config : "pyproject.toml" | resource;
```

#### `register(config)`
Registra un servizio o manager nel container DI.
```dsl
services | foreach(register);
```

### 10. Utility

#### `print(value)`
Stampa un valore e lo ritorna (utile per debug).
```dsl
debug : value | print;
```

## Operatori

### Aritmetici
- `+` Addizione / Concatenazione
- `-` Sottrazione
- `*` Moltiplicazione
- `/` Divisione
- `%` Modulo
- `^` Potenza

### Logici
- `==` Uguale
- `!=` Diverso
- `>` Maggiore
- `<` Minore
- `>=` Maggiore o uguale
- `<=` Minore o uguale
- `and` AND logico
- `or` OR logico
- `not` NOT logico

### Pipe
- `|` Passa l'output di un'espressione come input alla successiva

## Pattern Comuni

### Caricamento e Registrazione Servizi
```dsl
configuration : "pyproject.toml" | resource | format | convert(dict, "toml");

services : configuration 
    | filter(("message", "persistence"))
    | items
    | transform({
        "path": "infrastructure/{@.0}/{@.1.backend.adapter}.py";
        "service": "@.0";
        "adapter": "adapter";
    })
    | foreach(register);
```

### Conditional Service Loading
```dsl
environment : "production";

logger : environment | match({
    "@ == 'production'": "infrastructure/log/otel.py";
    "@ == 'development'": "infrastructure/log/console.py";
}) | resource | register;
```

### Parallel Processing with Fallback
```dsl
results : data_items 
    | parallel(process_item)
    | catch(fallback_processor);
```

### Retry with Timeout
```dsl
api_result : endpoint 
    | timeout(max_seconds=10)
    | retry(attempts=3, delay=2);
```

## Best Practices

1. **Usa `include` per modularità**: Separa costanti e configurazioni in file dedicati
2. **Sfrutta il pipe operator**: Rende il codice più leggibile e dichiarativo
3. **Gestisci sempre gli errori**: Usa `catch`, `retry`, `fallback` per robustezza
4. **Documenta con commenti**: Usa `#` per spiegare logiche complesse
5. **Nomina variabili chiaramente**: Usa snake_case e nomi descrittivi
6. **Testa incrementalmente**: Usa `print` per debuggare step intermedi

## Esempi Avanzati

### Service Mesh Configuration
```dsl
include("services.dsl");

mesh : services
    | filter(active_services)
    | transform({
        "name": "@.service";
        "endpoint": "@.host" + ":" + "@.port";
        "health_check": "@.endpoint" + "/health";
    })
    | parallel(register_service)
    | all_completed;
```

### Multi-Environment Deployment
```dsl
env : "ENV" | resource;

deployment : env | match({
    "@ == 'prod'": prod_config;
    "@ == 'staging'": staging_config;
    "@ == 'dev'": dev_config;
}) | chain((
    validate_config,
    deploy_services,
    run_health_checks
));
```

### Resilient API Call
```dsl
api_response : {
    "url": "https://api.example.com/data";
    "method": "GET";
}
    | timeout(max_seconds=30)
    | retry(attempts=3, delay=5)
    | catch(cached_response)
    | transform(response_schema);
```
