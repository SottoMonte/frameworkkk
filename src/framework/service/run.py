import asyncio
import sys
import os
from framework.service.inspector import framework_log

imports = {
    #'loader': 'framework/manager/loader.py'
    'loader': 'framework/service/load.py',
    'flow': 'framework/service/flow.py',
    'language': 'framework/service/language.py'
}

import os
import requests
import hashlib

# =========================================================================
# 4. FUNZIONE 'TEST' MODIFICATA
# =========================================================================

def map_failed_tests2(result) -> set[tuple[str, str]]:
    """
    Estrae il percorso del file e il nome completo del metodo di test fallito 
    (FAIL o ERROR).
    Ritorna un set di tuple: {(path_del_file, nome_metodo_completo), ...}
    """
    failed_set: set[tuple[str, str]] = set()

    # Combina Failures (F) e Errors (E)
    all_issues = result.failures + result.errors

    for test, _ in all_issues:
        # Il nome del test viene formattato come: test_method (file.py.TestClass)
        # Esempio: test_post (src/infrastructure/message/console.test.py.Testadapter)
        
        test_id: str = test.id()
        
        # Scomponiamo l'ID
        parts = test_id.split('.')
        # L'ultimo elemento è il nome del metodo (es. test_post)
        method_name = parts[-1]
        # L'elemento prima dell'ultimo contiene il file e la classe (es. src/.../console.test.py.Testadapter)
        
        # Rimuoviamo il nome della classe per isolare il percorso del file
        # Otteniamo il percorso del file (es. src/infrastructure/message/console.test.py)
        # La logica è complessa a causa della formattazione standard di unittest,
        # ma possiamo usare il nome del file fornito nel Traceback per la sicurezza.
        
        # Basandoci sul traceback, il formato è: test_metodo (percorso/file.test.py.TestClasse)
        # Usiamo il nome del file di test come chiave principale.
        
        # Estrarre il percorso del file (più semplice se conosciamo il formato)
        # Esempio: 'src/infrastructure/message/console.test.py'
        # Cerchiamo il primo elemento che inizia con 'src/'
        file_path_parts = [p for p in parts if 'src/' in p]
        if file_path_parts:
            # Rimuoviamo il nome della classe se presente
            file_path = file_path_parts[0].split('Test')[0].split('test.')[0] + '.test.py'
        else:
            # Fallback se la formattazione è inattesa
            continue
            
        failed_set.add((file_path, method_name))
        
    return failed_set

def map_failed_tests(result) :
    """
    Estrae il percorso del file, il nome della classe del test e il nome completo 
    del metodo di test fallito (FAIL o ERROR).
    
    Ritorna un set di tuple: 
    {(path_del_file, nome_classe_del_test, nome_metodo), ...}
    """
    failed_set = set()

    # Combina Failures (F) e Errors (E)
    all_issues = result.failures + result.errors

    for test, _ in all_issues:
        # L'ID del test è solitamente nel formato:
        # <nome_modulo>.<nome_classe>.<nome_metodo>
        # Esempio: src.infrastructure.message.console.Testadapter.test_post
        test_id: str = test.id()
        
        parts: list[str] = test_id.split('.')
        
        if len(parts) < 3:
            # Caso anomalo, saltiamo
            continue
            
        # 1. Nome del Metodo (l'ultimo elemento)
        method_name: str = parts[-1]
        
        # 2. Nome della Classe del Test (il penultimo elemento)
        test_class_name: str = parts[-2]
        
        # 3. Percorso del File/Modulo
        # I primi elementi compongono il nome del modulo (es. src.infrastructure.message.console)
        module_name: str = ".".join(parts[:-2])
        
        # Tenta di convertire il nome del modulo in un percorso di file
        file_path: str = module_name
        
        try:
            # Importa il modulo per trovare il percorso fisico del file
            # NOTA: Questo richiede che il modulo sia importabile nell'ambiente di esecuzione
            modulo_obj = __import__(module_name, fromlist=[''])
            if hasattr(modulo_obj, '__file__'):
                # Ottiene il percorso assoluto e rimuove le estensioni di bytecode
                path_assoluto = modulo_obj.__file__
                if path_assoluto.endswith(('.pyc', '.pyo')):
                    path_assoluto = path_assoluto[:-1]
                
                # Per replicare la pulizia come nel codice precedente, potresti dover 
                # rimuovere parti non necessarie (ad esempio, renderlo relativo al root del progetto).
                # Usiamo il percorso pulito
                file_path = path_assoluto
                
        except Exception:
            # Fallback al nome del modulo se non riusciamo a trovare il file fisico
            pass

        # Aggiungiamo la tupla con il nome della classe
        failed_set.add((file_path, test_class_name, method_name))
            
    return failed_set

async def discover_and_run_tests():
    import unittest
    import json
    import framework.service.language as language
    
    # Pattern personalizzato per i test
    test_dir = './src'
    test_suite = unittest.TestSuite()
    all_contract_hashes: dict[str, any] = {}

    #di['module_cache']['framework/service/language.py'] = language
    text = await language.resource(path="pyproject.toml")
    framework_log("DEBUG", "pyproject.toml loaded successfully", emoji="📜")
    #config = await language.format(text,**{})
    config = await language.convert(text, dict, 'toml')

    #await loader.bootstrap_core(config)
    
    # 1. FASE DI SCOPERTA E GENERAZIONE HASH
    for root, dirs, files in os.walk(test_dir):
        for file in files:
            if file.endswith('.test.py'):
                module_path_rel = os.path.join(root, file).replace('./','')
                main_path_rel = module_path_rel.replace('.test.py','.py')
                json_path = main_path_rel.replace('.py', '.contract.json')
                
                framework_log("DEBUG", f"Generazione contratto per: {module_path_rel}", emoji="🔍")
                try:
                    
                    #hashes = await language.generate_and_validate_contract_json(main_path_rel)
                    hashes = await language.generate(main_path_rel,'module')
                    all_contract_hashes |= hashes
                    
                    # --- SALVATAGGIO JSON (Simulato) ---
                    json_content = json.dumps(hashes, indent=4)
                    # Simula il salvataggio del file .contract.json
                    # await language.backend(path=json_path, content=json_content, mode='w')
                    framework_log("INFO", f"Contratto JSON salvato (Simulato) in: {json_path}", emoji="✅")
                    
                except Exception as e:
                    framework_log("ERROR", f"Errore critico nella generazione del contratto: {e}", emoji="❌")

                    continue
                    
                # 2. FASE DI CARICAMENTO TEST (per l'esecuzione)
                try:
                    # Carica il modulo di test usando il framework per DI/Filtro
                    module_name = os.path.splitext(file)[0]
                    # language.resource caricherà e *filtrerà* il modulo usando il .contract.json appena creato
                    module = await language.resource(path=module_path_rel)
                    print(dir(module_path_rel))
                    # Aggiungi i test dal modulo filtrato
                    test_suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(module))
                except Exception as e:
                    import traceback
                    framework_log("ERROR", f"Errore nell'importazione/filtro del modulo: {main_path_rel}, {e}", emoji="❌")
                    # traceback.print_exc() # Still keep for very deep debug if needed, but framework_log might handle it
    
    checking = estrai_test_da_suite(test_suite)
    def filtra_contratti_test_compattato(
    all_contract_hashes,
    checking
):
        """
        Filtra il dizionario completo (all_contract_hashes) per mantenere SOLO gli hash
        dei metodi di test presenti nel dizionario di controllo (checking).
        """
        
        a =  {
            file_path.replace('.test.py','.py'): {
                '__module__'if 'TestModule' in name else name.replace('Test',''):{
                    test_name: test_value
                    for test_name,test_value in all_contract_hashes.get(file_path.replace('.test.py','.py'), {}).get('__module__'if 'TestModule' in name else name.replace('Test',''), {}).items()
                    #if test_name in test_groups.keys()
                }
                for name, test_groups in test_groups.items()

            }
            # Ciclo sui file di 'checking'
            for file_path, test_groups in checking.items()
        
            
        }
        return a
    return filtra_contratti_test_compattato(all_contract_hashes,checking),test_suite

def estrai_test_da_suite(suite: any) -> dict[str, dict[str, dict[str, str]]]:
    """
    Attraversa ricorsivamente un oggetto unittest.suite.TestSuite annidato
    e restituisce un dizionario strutturato nel formato:
    {
        "percorso/file.py": {
            "nome_classe_o_modulo": {
                "nome_metodo": "TO_BE_HASHED" 
            }
        }
    }
    """
    import unittest
    # Usiamo un dizionario temporaneo per la struttura intermedia
    risultato_intermedio: dict[str, dict[str, dict[str, str]]] = {}
    
    # --- Funzione Helper Ricorsiva ---
    def _raccogli_test(s: any) -> None:
        for test in s:
            if isinstance(test, unittest.TestSuite):
                # Caso 1: È una sottosuite. Chiamiamo ricorsivamente.
                _raccogli_test(test)
            
            elif isinstance(test, unittest.TestCase):
                # Caso 2: È un TestCase effettivo (il nodo finale)
                
                # 1. Estrai il nome del metodo
                nome_metodo: str = getattr(test, '_testMethodName', 'unknown_method')
                
                # 2. Estrai il nome della classe del test (usato per la chiave intermedia)
                nome_classe_test: str = test.__class__.__name__
                # Usiamo 'adapter' come nell'esempio per la coerenza, 
                # ma in genere sarebbe il nome della classe.
                nome_gruppo: str = nome_classe_test # o test.__class__.__name__ 
                
                # 3. Estrai il percorso del file / modulo
                nome_modulo: str = test.__class__.__module__
                percorso_test_pulito: str = nome_modulo
                
                # Tenta di trovare il percorso fisico del file sorgente
                try:
                    # Importa il modulo
                    modulo_obj: any = __import__(nome_modulo, fromlist=[''])
                    if hasattr(modulo_obj, '__file__'):
                        percorso_file_assoluto: str = modulo_obj.__file__
                        # Pulizia .pyc/.pyo
                        if percorso_file_assoluto.endswith(('.pyc', '.pyo')):
                             percorso_file_assoluto = percorso_file_assoluto[:-1]
                            
                        percorso_test_pulito = percorso_file_assoluto
                        
                except Exception:
                    # Fallback al nome del modulo
                    pass
                
                # --- Costruzione del Dizionario ---
                percorso_chiave = percorso_test_pulito
                
                if percorso_chiave not in risultato_intermedio:
                    risultato_intermedio[percorso_chiave] = {}
                
                if nome_gruppo not in risultato_intermedio[percorso_chiave]:
                    risultato_intermedio[percorso_chiave][nome_gruppo] = {}
                    
                # Inserisci il metodo di test con il segnaposto "TO_BE_HASHED"
                risultato_intermedio[percorso_chiave][nome_gruppo][nome_metodo] = "TO_BE_HASHED"

    # Esegui la ricorsione
    _raccogli_test(suite)
    
    # Rimuovi i percorsi che sono solo nomi di moduli (se possibile) e normalizza
    risultato_finale: dict[str, dict[str, dict[str, str]]] = {}
    
    # Piccola normalizzazione per pulire l'output
    for path, groups in risultato_intermedio.items():
            risultato_finale[path] = groups

    return risultato_finale

def test():
    """Funzione di avvio principale per la generazione del contratto e l'esecuzione dei test."""
    import unittest
    import asyncio
    
    framework_log("INFO", "🔍 Avvio scoperta e generazione contratti test...", emoji="🔍")
    
    # Scopri e genera i contratti, poi esegui i test
    all_contract_hashes, suite_test = asyncio.run(discover_and_run_tests())
    
    # Verifica quanti test sono stati scoperti
    test_count = suite_test.countTestCases()
    framework_log("INFO", f"📊 Scoperti {test_count} test", emoji="📊")
    
    if test_count == 0:
        framework_log("WARNING", "⚠️ Nessun test scoperto! Verifica i file .test.py", emoji="⚠️")
        return
    
    # Esegui la fase di scoperta, generazione del contratto ed esecuzione
    suite = suite_test
    runner = unittest.TextTestRunner(verbosity=2)
    framework_log("INFO", "🧪 INIZIO ESECUZIONE TEST", emoji="🧪")
    result = runner.run(suite)
    
    # Analizza i risultati
    framework_log("INFO", f"✅ Test eseguiti: {result.testsRun}", emoji="✅")
    framework_log("INFO", f"❌ Falliti: {len(result.failures)}", emoji="❌")
    framework_log("INFO", f"💥 Errori: {len(result.errors)}", emoji="💥")
    
    fail = map_failed_tests(result)
    if fail:
        framework_log("ERROR", f"TEST FALLITI O ERRORE NEI TEST: {fail}", emoji="❌")
        for f in fail:
            try:
                del all_contract_hashes[f[0].replace('.test.py','.py')]['__module__'if 'TestModule' in f[1] else f[1].replace('Test','')][f[2].replace('test_','')]
            except KeyError:
                pass
    
    framework_log("INFO", f"📝 Salvataggio contratti aggiornati...", emoji="📝")
    for file_path, groups in all_contract_hashes.items():
        with open(file_path.replace('.py','.contract.json'), "w") as f:
            converted = asyncio.run(language.convert(groups,str,'json'))
            f.write(converted)
    
    framework_log("INFO", "🏁 FINE ESECUZIONE TEST", emoji="🏁")
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


def application(tester=None,**constants):
    args = constants.get('args', sys.argv)
    
    # --- Gestione Generazione Contratto ---
    if '--generate-contract' in args:
        framework_log("INFO", "🛠️ Avvio rigenerazione contratti su richiesta...", emoji="🛠️")
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        
        async def regenerate_all():
            test_dir = './src'
            count = 0
            for root, dirs, files in os.walk(test_dir):
                for file in files:
                    if file.endswith('.py') and not file.endswith('.test.py') and not file.startswith('__'):
                        main_path = os.path.join(root, file)
                        try:
                            await loader.generate_checksum(main_path)
                            count += 1
                        except Exception:
                            pass
            framework_log("INFO", f"✅ Rigenerati {count} contratti.", emoji="✅")

        try:
             event_loop.run_until_complete(regenerate_all())
             framework_log("INFO", "🏁 Generazione completata. Uscita.", emoji="🏁")
             return
        except Exception as e:
             framework_log("ERROR", f"❌ Errore rigenerazione: {e}", emoji="❌")
             return

    # --- Gestione Test ---
    if '--test' in args:
        test()
        return

    # --- Avvio Normale Applicazione ---
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    
    try:
        dsl = event_loop.run_until_complete(loader.resource(path='framework/service/bootstrap.dsl'))
        config_data = event_loop.run_until_complete(language.execute_dsl_file(dsl.get('data')))
        
        # Schedule Triggers (Cron & Events) from DSL configuration
        if isinstance(config_data, dict) and '__triggers__' in config_data:
            framework_log("INFO", f"📅 Scheduling {len(config_data['__triggers__'])} triggers from DSL", emoji="📅")
            for trigger_key, action in config_data['__triggers__']:
                # Cron Trigger
                if isinstance(trigger_key, (list, tuple)) and any(x == '*' for x in trigger_key):
                    event_loop.create_task(flow.cron(trigger_key, action, context={'system': True}))
                
                # Event Trigger
                elif isinstance(trigger_key, tuple) and trigger_key[0] == 'CALL':
                    async def event_listener(t_key, act):
                        framework_log("INFO", f"👂 Avvio listener evento: {t_key[1]}", emoji="👂")
                        ctx = {'system': True}
                        while True:
                            try:
                                res = await language.DSLVisitor(language.dsl_functions).execute_call(t_key, ctx)
                                is_valid = res and isinstance(res, dict) and res.get('success')
                                data = res.get('data') if is_valid else None
                                
                                if is_valid and data:
                                    framework_log("INFO", f"🔔 Evento rilevato: {t_key[1]}", emoji="🔔")
                                    await language.DSLVisitor(language.dsl_functions).visit(act, ctx | {'@event': data})
                                else:
                                    await asyncio.sleep(1)
                            except Exception as e:
                                framework_log("ERROR", f"❌ Listener Error {t_key[1]}: {e}", emoji="❌")
                                await asyncio.sleep(5)

                    event_loop.create_task(event_listener(trigger_key, action))

    except Exception as e:
        framework_log("ERROR", f"❌ Errore durante l'esecuzione del DSL: {e}", emoji="❌")
    
    event_loop.run_forever()