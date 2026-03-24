import os
import asyncio

class tester:
    def __init__(self, **config):
        self.args = config.get('args')
        self.loader = config.get('loader')
        if '--test' in self.args:
            asyncio.create_task(self.run())

    async def run(self, **constants):
        diagnostic.log("INFO", "Avvio esecuzione suite di test...", emoji="🧪")
        interp = language.Interpreter()
        await interp.start()
        for root, _, files in os.walk('./src'):
            for file in files:
                if file.endswith('.test.dsl'):
                    await self.dsl(interp, path=os.path.join(root, file).replace('./', ''))
        

    async def dsl(self, interp, **kwargs):

        path = kwargs.get('path')
        diagnostic.log("INFO", f"Esecuzione test DSL in {path}", emoji="🧪")
        # ── caricamento e parsing ─────────────────────────────────────────────
        res    = self.loader.resource(path)
        source = flow.value_of(res) if flow.is_result(res) else res
        if not isinstance(source, str):
            diagnostic.log("ERROR", f"Risorsa non stringa per {path}", emoji="❌")
            return {"success": False, "errors": ["risorsa non valida"]}

        parser = language.create_parser()
        ast    = language.parse(source, parser)
        if isinstance(ast, Exception):
            diagnostic.log("ERROR", f"Errore di parsing DSL in {path}: {ast}", emoji="❌")
            return {"success": False, "errors": [str(ast)]}

        # ── esecuzione ────────────────────────────────────────────────────────
        ctx    = await interp.run(path, ast,"tester", env=language.DSL_FUNCTIONS) or {}
        
        '''errors = [
            err
            for k, v in ctx.items()
            if not k.startswith("_") and flow.is_result(v) and not v["success"]
            for err in v["errors"]
        ]
        if errors:
            diagnostic.log("ERROR", f"Errore in {path}: {errors}", emoji="❌")
            return {"success": False, "errors": errors}'''

        # ── esecuzione test suite ─────────────────────────────────────────────
        test_suite = ctx.get('test_suite', []) or []
        if isinstance(test_suite, dict):
            test_suite = [test_suite]

        results = {"total": 0, "passed": 0, "failed": 0, "errors": [], "details": []}

        for i, test in enumerate(test_suite):
            if not isinstance(test, dict): continue
            results["total"] += 1
            target   = test.get('action')
            args     = test.get('inputs', ())
            expected = test.get('outputs')
            assert_  = test.get('assert')

            try:
                if isinstance(args, dict):
                    received = await interp.invoke(target, [], args)
                else:
                    received = await interp.invoke(target, args)

                if assert_(received=received, expected=expected):
                    results["passed"] += 1
                    results["details"].append({"target": target, "status": "OK"})
                    diagnostic.log("INFO", f"OK - Test N.{i}: {test['note']}", emoji="✅")
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "target": target, "status": "FAIL",
                        "expected": expected, "received": received,
                    })
                    diagnostic.log("WARNING", f"FAIL - Test N.{i}: {test['note']}",
                                  affirmed=assert_, expected=expected,
                                  received=received, emoji="❌")

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"target": target, "error": str(e)})
                results["details"].append({"target": target, "status": "ERROR", "message": str(e)})
                diagnostic.log("ERROR", f"Test N.{i}: ERROR", error=str(e), emoji="⚠️")

        status = "PASSED" if results["failed"] == 0 else "FAILED"
        diagnostic.log("INFO", f"DSL Test {path or 'Inline'}: {status}",
                      total=results["total"], passed=results["passed"],
                      failed=results["failed"])

        return {"success": results["failed"] == 0, "data": results}