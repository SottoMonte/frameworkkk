import os
import asyncio

# Alias abbreviati → percorso src relativo
_FILTER_ALIASES: dict[str, str] = {
    "managers":        "src/framework/manager",
    "ports":           "src/framework/port",
    "services":        "src/framework/service",
    "infrastructure":  "src/infrastructure",
}

class tester:
    def __init__(self, **config):
        self.args      = config.get('args', [])
        self.loader    = config.get('loader')
        self.defender  = config.get('defender')
        self.messenger = config.get('messenger')

    # ── helpers ──────────────────────────────────────────────────────────────

    def _resolve_filter(self) -> str | None:
        """Ritorna il prefisso di percorso su cui filtrare, o None (tutto).

        Esempi di input → output:
            managers                   → src/framework/manager
            managers/defender          → src/framework/manager/defender
            ports                      → src/framework/port
            infrastructure             → src/infrastructure
            infrastructure/authentication → src/infrastructure/authentication
            src/qualunque/percorso     → src/qualunque/percorso  (raw)
        """
        args = list(self.args)
        if '--test' not in args:
            return None
        idx = args.index('--test')
        if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
            raw = args[idx + 1]
            # 1) Alias esatto  →  managers
            if raw in _FILTER_ALIASES:
                return _FILTER_ALIASES[raw]
            # 2) Alias + sub   →  managers/defender  oppure  infrastructure/authentication
            for alias, base in _FILTER_ALIASES.items():
                if raw.startswith(alias + '/'):
                    sub = raw[len(alias) + 1:]
                    return f"{base}/{sub}"
            # 3) Percorso src diretto (fallback)
            return raw
        return None  # Nessun filtro → tutti i test

    def _matches_filter(self, path: str, prefix: str | None) -> bool:
        """True se il file deve essere eseguito dato il filtro attivo."""
        if prefix is None:
            return True
        # Normalizza separatori
        norm_path   = path.replace('\\', '/')
        norm_prefix = prefix.replace('\\', '/')
        return norm_path.startswith(norm_prefix)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        if '--test' in self.args:
            await self.run()

    async def run(self, **constants):
        prefix = self._resolve_filter()
        label  = prefix or 'tutti'
        diagnostic.log("INFO", f"Avvio esecuzione suite di test… filtro: {label}", emoji="🧪")

        interp = language.Interpreter()
        await interp.start()
        await interp.create_session("tester", env=language.DSL_FUNCTIONS|{'resource':self.loader.resource})

        for root, _, files in os.walk('./src'):
            for file in files:
                if not file.endswith('.test.dsl'):
                    continue
                path = os.path.join(root, file).replace('./', '')
                if not self._matches_filter(path, prefix):
                    continue
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