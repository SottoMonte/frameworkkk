import asyncio
from typing import List, Dict, Any, Callable
import re
import traceback

class executor:
    def __init__(self, **constants):
        self.defender = constants.get('defender')
        self.language = constants.get('language')
        self.messenger = constants.get('messenger')
        self.models = constants.get('models')
        self.interpreter = self.language.Interpreter(custom_types=self.models)

    # ── INTERPRETER ────────────────────────────────────────────────────────────────

    async def stop(self):
        await self.interpreter.stop()
    
    async def start(self):
        await self.interpreter.start()

    async def add_file(self, name, source):
        return await self.interpreter.add_file(name, source)

    async def create_session(self, session, env={}):
        return await self.interpreter.create_session(session, env|self.language.DSL_FUNCTIONS)

    async def run_session(self, session, file, env={}):
        return await self.interpreter.run_session(session, file, env|self.language.DSL_FUNCTIONS)
        
    # ── PROVIDER ────────────────────────────────────────────────────────────────

    def _select_provider(self, requirements: Dict[str, Any]) -> Any:
        """Seleziona il provider che meglio soddisfa i requirements."""
        if not self.providers:
            return None
            
        if not requirements:
            return self.providers[-1] # Default behavior (last one) or first? Original code used -1.
            
        best_provider = None
        best_score = -1
        
        for provider in self.providers:
            score = 0
            capabilities = getattr(provider, 'capabilities', {})
            
            # Calcola score basato su requirements e capabilities
            # Esempio semplice: +1 per ogni match esatto
            match = True
            for req_key, req_val in requirements.items():
                cap_val = capabilities.get(req_key)
                if cap_val != req_val:
                    match = False
                    break
            
            if match:
                # Se tutti i requirements sono soddisfatti, questo è un candidato.
                # Potremmo avere logiche più complesse di scoring.
                return provider
                
        # Se nessun match esatto, ritorna l'ultimo (fallback) o None?
        # Per ora fallback all'ultimo come comportamento di default
        return self.providers[-1]

    # ── API ────────────────────────────────────────────────────────────────


    async def first_completed(self, **constants):
        """Attende il primo task completato e restituisce il suo risultato."""
        operations = constants.get('operations', [])
        #await self.messenger.post(domain='debug',message="⏳ Attesa della prima operazione completata...")

        while operations:
            finished, unfinished = await asyncio.wait(operations, return_when=asyncio.FIRST_COMPLETED)

            for operation in finished:
                transaction = operation.result()
                if transaction:
                    # framework_log("DEBUG", f"Transazione completata: {type(transaction)}", emoji="💼")
                    if 'success' in constants:
                        transaction = await constants['success'](transaction=transaction,profile=operation.get_name())
                    
                    # Ensure transaction is a dict to attach parameters
                    if isinstance(transaction, list):
                        transaction = {"success": True, "data": transaction, "errors": []}
                    
                    if isinstance(transaction, dict):
                        #framework_log("DEBUG", f"✅ Executor: transazione valida trovata per {operation.get_name()}")
                        for task in unfinished:
                            task.cancel()
                        transaction.setdefault('parameters', getattr(operation, 'parameters', {}))
                        return transaction
                    
                    for task in unfinished:
                        task.cancel()
                    return {"success": True, "data": transaction, "errors": []}

                operations = unfinished

            error_msg = "⚠️ Nessuna transazione valida completata"
            #await messenger.post(domain='debug',message=error_msg)
            return None

    async def all_completed(self, **constants) -> Dict[str, Any]:
        tasks: List[asyncio.Future] = constants.get('tasks', [])
    
        # Lista per raccogliere i dettagli degli errori da ogni task
        detailed_errors = []
        
        # return_exceptions=True: le eccezioni sono restituite come risultati
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 1. Analisi dei Risultati Dettagliata
        for result in results:
            if isinstance(result, Exception):
                
                # Questa funzione stampa il traceback completo sul tuo log/console
                traceback.print_exception(type(result), result, result.__traceback__)
                
                # Un task è fallito. Registra il traceback completo.
                
                # Ottieni il traceback completo (come stringa)
                error_trace = traceback.format_exception(type(result), result, result.__traceback__)
                full_error_log = "".join(error_trace)
                
                # Aggiungi il dettaglio all'elenco degli errori
                detailed_errors.append(full_error_log)

        
        # Se ci sono errori dettagliati, il risultato complessivo è un fallimento logico
        if any(result.get('success', False) is not True for result in results):
            return {"success": False, "results": results, "errors": detailed_errors}
        
        return {"success": True, "results": results}

    async def chain_completed(self, **constants) -> Dict[str, Any]:
        """Esegue i task in sequenza, aspettando il completamento di ciascuno prima di passare al successivo."""
        tasks = constants.get('tasks', [])
        results = []

        #await self.messenger.post(domain='debug',message="🔄 Avvio esecuzione sequenziale delle operazioni...")

        try:
            for task in tasks:
                try:
                    result = await task(**constants)
                    results.append(result)
                    #await messenger.post(domain='debug', message=f"✅ Task completato: {result}")
                except Exception as e:
                    #await messenger.post(domain='debug', message=f"❌ Errore nel task {task}: {e}")
                    pass

            return {"state": True, "result": results, "error": None}

        except Exception as e:
            error_msg = f"❌ Errore in chain_completed: {str(e)}"
            #await messenger.post(domain='debug', message=error_msg)
            return {"state": False, "result": None, "error": error_msg}

    async def together_completed(self, **constants) -> Dict[str, Any]:
        """Esegue tutti i task contemporaneamente senza attendere il completamento di tutti."""
        tasks = constants.get('tasks', [])

        #await messenger.post(domain='debug', message="🚀 Avvio esecuzione simultanea delle operazioni...")

        try:
            for task in tasks:
                asyncio.create_task(task)

            #await messenger.post(domain='debug', message="✅ Tutti i task sono stati avviati in background.")
            return {"state": True, "result": "Tasks avviati in background", "error": None}

        except Exception as e:
            error_msg = f"❌ Errore in together_completed: {str(e)}"
            #await messenger.post(domain='debug', message=error_msg)
            return {"state": False, "result": None, "error": error_msg}