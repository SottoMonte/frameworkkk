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
                    print(file)
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
                    print(await self.dsl(path= module_path))
                    exit(1)


    async def dsl(self, **kwargs):
        """
        Esegue i test definiti in un file DSL o in una struttura dati DSL.
        Supporta la verifica di hash (integrità) e casi di test TDD.
        """
        from framework.service.load import resource
        
        path = kwargs.get('path')
        parsed = kwargs.get('data') or kwargs.get('parsed')
        #path = "src/framework/service/data_driven.test.dsl"
        
        res = await resource(path)
        ok = res.get('outputs',path)
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
        s = language.parse(ok,parser)
        parsed = await visitor.run(s)
        print("[ERRORI]:",parsed.get('errors'))
        ooout = parsed.get('outputs')
        #exit(1)
        # 2. Esecuzione Test Suite (TDD)
        
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
        #print("##########",test_suite)
        for test in test_suite:
            if not isinstance(test, dict): continue
            results["total"] += 1
            target = test.get('target')
            args = test.get('inputs', ())
            #if not isinstance(args, (list, tuple)):
            #    args = (args,)
            
            expected = test.get('output')
            
            try:
                actual, _ = await visitor.visit_call({'type':'call','name':target},ooout, args)
                actual = actual.get('outputs')
                if actual == expected:
                    results["passed"] += 1
                    results["details"].append({"target": target, "status": "OK"})
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "target": target, 
                        "status": "FAIL", 
                        "expected": expected, 
                        "actual": actual
                    })
            except Exception as e:
                #raise e
                results["failed"] += 1
                results["errors"].append({"target": target, "error": str(e)})
                results["details"].append({"target": target, "status": "ERROR", "message": str(e)})

        framework_log("INFO", f"DSL Test {path or 'Inline'}: {'PASSED' if results['failed'] == 0 else 'FAILED'}", 
                      total=results["total"], passed=results["passed"], failed=results["failed"])
        
        return {
            "success": results["failed"] == 0,
            "data": results
        }