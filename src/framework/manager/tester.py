import os
import asyncio
from framework.service.diagnostic import framework_log
import framework.service.language as language
import framework.service.flow as flow


class tester:

    def __init__(self, **constants):
        self.sessions  = {}
        self.providers = constants.get('providers', [])

    async def run(self, **constants):
        framework_log("INFO", "Avvio esecuzione suite di test...", emoji="🧪")
        test_dir = './src'
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.endswith('.test.dsl'):
                    path = os.path.join(root, file).replace('./', '')
                    await self.dsl(path=path)

    async def dsl(self, **kwargs):
        """Esegue i test definiti in un file DSL."""
        from framework.service.load import resource

        path = kwargs.get('path')
        print(path)

        # ── caricamento e parsing ─────────────────────────────────────────────
        res    = await resource(path)
        source = flow.value_of(res) if flow.is_result(res) else res
        if not isinstance(source, str):
            framework_log("ERROR", f"Risorsa non stringa per {path}", emoji="❌")
            return {"success": False, "errors": ["risorsa non valida"]}

        parser  = language.create_parser()
        ast     = language.parse(source, parser)
        if isinstance(ast, Exception):
            framework_log("ERROR", f"Errore di parsing DSL in {path}: {ast}", emoji="❌")
            return {"success": False, "errors": [str(ast)]}

        # ── esecuzione DAG ────────────────────────────────────────────────────
        dag = language.DAGGenerator(language.DSL_FUNCTIONS)
        raw = await dag.run(ast) or {}

        # Controlla nodi falliti nel contesto grezzo
        errors = [
            err
            for k, v in raw.items()
            if not k.startswith("_")           # salta nodi sintetici
            and flow.is_result(v)
            and not v["success"]
            for err in flow.errors_of(v)
        ]
        if errors:
            framework_log("ERROR", f"Errore DAG in {path}: {errors}", emoji="❌")
            return {"success": False, "errors": errors}

        ctx = language.DAGGenerator.clean(raw)
        #print(ctx)
        if not isinstance(ctx, dict):
            print(ctx); return

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
                    received = await dag._interp.invoke(target, [], args)
                elif isinstance(args, list):
                    received = await dag._interp.invoke(target, args)
                else:
                    received = await dag._interp.invoke(target, args)

                # invoke restituisce un NodeResult — estraiamo il valore
                #received = flow.value_of(received)

                if assert_(received=received, expected=expected):
                    results["passed"] += 1
                    results["details"].append({"target": target, "status": "OK"})
                    framework_log("INFO", f"OK - Test N.{i}: {test['note']}", emoji="✅")
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "target": target, "status": "FAIL",
                        "expected": expected, "received": received,
                    })
                    framework_log("WARNING", f"FAIL - Test N.{i}: {test['note']}",
                                  affirmed=assert_, expected=expected,
                                  received=received, emoji="❌")

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"target": target, "error": str(e)})
                results["details"].append({"target": target, "status": "ERROR", "message": str(e)})
                framework_log("ERROR", f"Test N.{i}: ERROR", error=str(e), emoji="⚠️")

        status = "PASSED" if results["failed"] == 0 else "FAILED"
        framework_log("INFO", f"DSL Test {path or 'Inline'}: {status}",
                      total=results["total"], passed=results["passed"],
                      failed=results["failed"])

        return {"success": results["failed"] == 0, "data": results}