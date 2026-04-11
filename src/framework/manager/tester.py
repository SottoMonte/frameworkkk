import os
import asyncio

class tester:
    def __init__(self, **config):
        self.args = config.get('args')
        self.loader = config.get('loader')
        self.defender = config.get('defender')
        self.messenger = config.get('messenger')

    async def start(self):
        if '--test' in self.args:
            await self.run()

    async def run(self, **constants):
        diagnostic.log("INFO", "Avvio esecuzione suite di test...", emoji="🧪")
        interp = language.Interpreter()
        await interp.start()
        await interp.create_session("tester", env=language.DSL_FUNCTIONS|{'resource':self.loader.resource})
        for root, _, files in os.walk('./src'):
            for file in files:
                if file.endswith('.test.dsl'):
                    path = os.path.join(root, file).replace('./', '')
                    print(path)
                    res    = await self.loader.resource(path)
                    source = flow.value_of(res) if flow.is_result(res) else res
                    await interp.add_file(path, source)
                    await self.dsl(interp, path)
        

    async def dsl(self, interp, path):
        # ── esecuzione ────────────────────────────────────────────────────────
        ctx    = await interp.run_session("tester", path,env={'messenger':self.messenger,'defender':self.defender,'resource':self.loader.resource})
        
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
                elif isinstance(args, (list, tuple)):
                    received = await interp.invoke(target, args)
                else:
                    received = await interp.invoke(target, [args])

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