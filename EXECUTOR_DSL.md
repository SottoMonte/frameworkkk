# Executor Methods in DSL

## Overview
Il DSL ora supporta l'accesso diretto ai metodi dell'`executor` usando la sintassi con il punto.

## Sintassi

### Accesso all'Executor
```dsl
# L'executor è disponibile come oggetto globale
executor_instance : executor;
```

### Chiamata ai Metodi

#### `executor.all_completed(tasks)`
Attende il completamento di tutti i task e ritorna i risultati aggregati.

**Sintassi DSL:**
```dsl
# Esempio concettuale (richiede task reali)
results : executor.all_completed(tasks=my_tasks);
```

**Ritorna:**
```json
{
  "success": true/false,
  "results": [...],
  "errors": [...]
}
```

#### `executor.first_completed(operations)`
Ritorna il primo task che completa con successo, cancellando gli altri.

**Sintassi DSL:**
```dsl
winner : executor.first_completed(operations=my_operations);
```

**Ritorna:**
```json
{
  "success": true,
  "data": {...},
  "parameters": {...}
}
```

#### `executor.chain_completed(tasks)`
Esegue i task in sequenza, uno dopo l'altro.

**Sintassi DSL:**
```dsl
sequential_results : executor.chain_completed(tasks=my_tasks);
```

**Ritorna:**
```json
{
  "state": true,
  "result": [...],
  "error": null
}
```

#### `executor.together_completed(tasks)`
Avvia tutti i task in background senza attendere il completamento (fire-and-forget).

**Sintassi DSL:**
```dsl
background_jobs : executor.together_completed(tasks=my_tasks);
```

**Ritorna:**
```json
{
  "state": true,
  "result": "Tasks avviati in background",
  "error": null
}
```

## Aliases Disponibili

Per comodità, sono disponibili anche alias globali:

```dsl
# Invece di executor.all_completed
results : all_completed(tasks=my_tasks);

# Invece di executor.first_completed  
winner : first_completed(operations=my_operations);

# Invece di executor.chain_completed
sequential : chain(tasks=my_tasks);
# oppure
sequential : sequential(tasks=my_tasks);

# Invece di executor.together_completed
background : fire_and_forget(tasks=my_tasks);
```

## Esempio Completo

```dsl
{
    # Definisci le operazioni da eseguire
    operations : (
        operation_a,
        operation_b,
        operation_c
    );
    
    # Esegui tutte le operazioni e attendi il completamento
    all_results : executor.all_completed(tasks=operations);
    
    # Oppure prendi solo la prima che completa
    fastest_result : executor.first_completed(operations=operations);
    
    # Oppure eseguile in sequenza
    sequential_results : executor.chain_completed(tasks=operations);
    
    # Oppure avviale in background
    background_jobs : executor.together_completed(tasks=operations);
}
```

## Note Tecniche

### Lazy Loading
L'executor viene caricato in modo lazy (solo quando necessario) per ottimizzare le performance.

### Async/Await
Tutti i metodi dell'executor sono asincroni e vengono automaticamente gestiti dal DSL visitor.

### Error Handling
Ogni metodo ritorna un oggetto strutturato con campi `success`/`state`, `result`/`data`, e `errors`/`error` per una gestione consistente degli errori.

## Integrazione con Altri Costrutti DSL

### Con Match/Switch
```dsl
result : executor.all_completed(tasks=operations)
    | match({
        "@.success == true": process_success;
        "true": handle_error;
    });
```

### Con Catch
```dsl
result : executor.all_completed(tasks=operations)
    | catch(fallback_handler);
```

### Con Transform
```dsl
results : executor.all_completed(tasks=operations)
    | transform({
        "total": "@.results | length";
        "successful": "@.results | filter(success == true) | length";
    });
```

## Estendibilità

Per aggiungere nuovi metodi dell'executor al DSL:

1. Aggiungi il metodo alla classe `ExecutorProxy` in `language.py`
2. Il metodo sarà automaticamente disponibile con la sintassi `executor.method_name()`
3. Opzionalmente, aggiungi un alias globale in `dsl_functions`
