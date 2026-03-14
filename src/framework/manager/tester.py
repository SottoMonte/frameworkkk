import unittest
import os
import types
import sys
import io
import asyncio
import inspect
from framework.service.diagnostic import framework_log
import framework.service.language as language
import framework.service.flow as flow

class tester():

    def __init__(self,**constants):
        self.sessions = dict()
        self.providers = constants.get('providers',[])

    async def run(self,**constants):
        framework_log("INFO", "Avvio esecuzione suite di test...", emoji="🧪")
        import framework.service.load as loader
        test_dir = './src'
        
        # Scorri tutte le sottocartelle e i file
        for root, dirs, files in os.walk(test_dir):
            for file in files:
                if file.endswith('.test.dsl'):
                    # Crea il nome del modulo di test per ciascun file trovato
                    module_path = os.path.join(root, file).replace('./','')
                    
                    # Importa il modulo di test dinamicamente via loader
                    '''parser = language.create_parser()
                    visitor = language.Interpreter(language.DSL_FUNCTIONS)
                    await flow.catch(
                        flow.step(flow.pipeline,
                            flow.step(loader.resource,path=module_path),
                            flow.step(language.parse,'@.inputs',parser),
                            flow.step(visitor.run,'@.inputs'),
                            flow.step(flow.log,"--->: {inputs}  \n"),
                        ),
                        flow.step(flow.log,"Errore: {errors[0]} "),
                    )'''
                    #await self.dsl(path= module_path)
                    async def add_one(x): return x+1
                    async def double(x): return x*2
                    async def sum_list(lst): 
                        print("###################",lst) 
                        return sum(lst)

                    def odd_trigger(): return int(time.time()) % 2 == 1

                    nodes = [
                        flow.node("start", lambda: [1,2,3]),
                        flow.foreach("inc_numbers", add_one, data_dep="start",),
                        flow.pipeline("process_numbers", [double], deps=["inc_numbers"]),
                        flow.node("sum", sum_list, deps=["process_numbers"]),
                        flow.retry(flow.node("fail_example", lambda: 1/0), retries=3)
                    ]

                    context = await flow.run(nodes)
                    for k,v in context.items():
                        print("\n",k, v)
                    exit(1)


    async def dsl(self, **kwargs):
        """
        Esegue i test definiti in un file DSL o in una struttura dati DSL.
        Supporta la verifica di hash (integrità) e casi di test TDD.
        """
        from framework.service.load import resource
        
        path = kwargs.get('path')
        parsed = kwargs.get('data') or kwargs.get('parsed')
        #path = "src/framework/service/factory.test.dsl"
        print(path)
        res = await resource(path)
        ok = res.get('output',path)
        #print(res)

        '''# 1. Verifica Integrità (Hash) se possibile
        integrity_results = {}
        source_path = parsed.get('source') or (path.replace('.test.dsl', '.py') if path and '.test.dsl' in path else None)
        
        if source_path:
            try:
                contract = await helper_get_contract(source_path)
                if contract:
                    integrity_results = await helper_verify_integrity(source_path, contract)
            except Exception as e:
                framework_log("WARNING", f"Errore verifica integrità per {source_path}: {e}")'''
        visitor = language.Interpreter(language.DSL_FUNCTIONS)
        parser = language.create_parser()
        s = language.parse(ok, parser)
        if isinstance(s, Exception):
            framework_log("ERROR", f"Errore di parsing DSL in {path}: {s}", emoji="❌")
            return {"success": False, "errors": [str(s)]}

        parsed = await visitor.run(s)
        
        if not parsed.get('success', False):
            framework_log("ERROR", f"Errore di esecuzione DSL in {path}: {parsed.get('errors')}", emoji="❌")
            ooout = {}
        else:
            ooout = parsed.get('output')
            if isinstance(ooout, Exception):
                framework_log("ERROR", f"Errore nel runtime DSL (ritorno) per {path}: {ooout}", emoji="❌")
                ooout = {}
        #exit(1)
        # 2. Esecuzione Test Suite (TDD)
        if not isinstance(ooout, dict):
            print(ooout)
            return
        test_suite = ooout.get('test_suite',[])
        if isinstance(test_suite, dict): test_suite = [test_suite]
        
        results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "details": [],
            "integrity": {}
        }

        # Esecuzione della test suite definita
        tested_targets = set()
        for i,test in enumerate(test_suite):
            if not isinstance(test, dict): continue
            results["total"] += 1
            target = test.get('action')
            #tested_targets.add(target)
            args = test.get('inputs', ())
            expected = test.get('outputs')
            assert_ = test.get('assert')
            
            try:
                if isinstance(args,list):
                    received = await visitor.invoke(target, args)
                elif isinstance(args,dict):
                    received = await visitor.invoke(target, [],args)
                else:
                    received = await visitor.invoke(target, args)
                
                check = assert_(received=received,expected=expected)
                if check:
                    results["passed"] += 1
                    results["details"].append({"target": target, "status": "OK"})
                    framework_log("INFO", f"OK - Test N.{i}: {test['note']} ", emoji="✅")
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "target": target, 
                        "status": "FAIL", 
                        "expected": expected, 
                        "received": received
                    })
                    framework_log("WARNING", f"FAIL - Test N.{i}: {test['note']}", affirmed=assert_,expected=expected, received=received, emoji="❌")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"target": target, "error": str(e)})
                results["details"].append({"target": target, "status": "ERROR", "message": str(e)})
                framework_log("ERROR", f"Test N.{i}: ERROR", error=str(e), emoji="⚠️")

        # 3. Verifica Copertura (Exports)
        '''exports = ooout.get('exports', {})
        if isinstance(exports, dict):
            for export_name in exports.keys():
                target_to_find = f"exports.{export_name}"
                if target_to_find not in tested_targets:
                    msg = f"Manca almeno un test per l'elemento esportato: {export_name}"
                    results["total"] += 1
                    results["failed"] += 1
                    results["errors"].append({"target": target_to_find, "error": msg})
                    results["details"].append({"target": target_to_find, "status": "FAIL", "message": msg})
                    framework_log("ERROR", msg, emoji="⚠️")'''

        framework_log("INFO", f"DSL Test {path or 'Inline'}: {'PASSED' if results['failed'] == 0 else 'FAILED'}", 
                      total=results["total"], passed=results["passed"], failed=results["failed"])
        
        return {
            "success": results["failed"] == 0,
            "data": results
        }