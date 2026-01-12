import os, sys, asyncio, types, inspect, uuid, json
from typing import Dict, Any, List, Optional, Set
from framework.service.context import container
import framework.service.flow as flow
import framework.service.language as language
from framework.service.inspector import (
    analyze_module, framework_log, _load_resource, 
    analyze_exception, estrai_righe_da_codice, backend
)
from framework.service.scheme import convert
from dependency_injector import providers

# imports: {"flow": "framework/service/flow.py", "language": "framework/service/language.py"};

class ValidationContext:
    def __init__(self, path: str, module: Any = None):
        self.path, self.module = path, module
        self.contract_json = path.replace('.py', '.contract.json')
        self.external, self.test_path, self.test_code, self.ana, self.is_dsl = {}, None, None, {}, False
        self.exports, self.validated, self.allowed = {}, {}, {'language'}

    async def load(self, strict=True):
        try:
            content = await _load_resource(path=self.contract_json)
            self.external = await convert(content, dict, 'json')
        except Exception as e:
            if strict: raise ImportError(f"Strict Policy: Module '{self.path}' cannot be loaded without a valid contract JSON. Run tests first.")
        
        for p, dsl in [(self.path.replace('.py', '.test.dsl'), True), (self.path.replace('.py', '.test.py'), False)]:
            try:
                c = await _load_resource(path=p)
                if c: self.test_code, self.test_path, self.is_dsl = c, p, dsl; break
            except: continue
        
        if self.test_code:
            self.ana = language.parse_dsl_file(self.test_code) if self.is_dsl else analyze_module(self.test_code, self.test_path)
        elif strict:
            raise ImportError(f"Strict Policy: Module '{self.path}' has no associated test file (.test.dsl or .test.py).")
        return self

    def resolve(self):
        raw = self.ana.get('exports', {}) if self.is_dsl else getattr(self.module, 'exports', {})
        self.exports = {str(k): str(v) for k, v in (raw if isinstance(raw, dict) else {}).items()}
        if not self.exports and self.external:
            for k, v in self.external.items():
                if k == '__module__' and isinstance(v, dict): self.exports.update({m: m for m in v})
                else: self.exports[k] = k
        self.exports['language'] = 'language'
        return self

    async def validate(self):
        # Always use strict=False for internal checksum generation during validation
        ccc_res = await generate_checksum(self.path, run_tests=False)
        ccc = ccc_res.get('data', {}).get(self.path, {})
        for g, hshs in self.external.items():
            valid = {m for m, h in hshs.items() if isinstance(h, dict) and ccc.get(g, {}).get(m, {}).get('production') == h.get('production') and ccc.get(g, {}).get(m, {}).get('test') == h.get('test')}
            if valid: self.validated[g] = valid

    def compute(self):
        if 'framework/service/load.py' in self.path: self.allowed.update({'resource', 'bootstrap', 'register', 'generate_checksum'})
        tested = {str(t.get('target')) for t in self.ana.get('test_suite', []) if isinstance(t, dict)} if self.is_dsl else None
        if self.is_dsl and not tested: tested = set(self.exports.keys())
        for pub, priv in self.exports.items():
            val = getattr(self.module, priv, None)
            if not val: continue
            if self.is_dsl:
                if pub in tested and (pub in self.validated.get('__module__', {}) or any(pub in vm for g, vm in self.validated.items() if g != '__module__')): self.allowed.add(pub)
            else:
                tp = {n.replace('Test',''): {f.replace('test_','') for f in d.get('data',{}).get('methods',{}) if f.startswith('test_')} for n, d in self.ana.items() if isinstance(d, dict)}
                if (inspect.isclass(val) and (tp.get(pub) or self.validated.get(pub))) or (inspect.isfunction(val) and pub in tp.get('__module__', {}) and pub in self.validated.get('__module__', {})): self.allowed.add(pub)

    def build(self) -> types.ModuleType:
        proxy = types.ModuleType(f"filtered:{self.path}"); proxy.__file__ = self.path
        proxy.language = getattr(self.module, 'language', language)
        for pub in self.allowed:
            attr = getattr(self.module, self.exports.get(pub, pub), None)
            if attr is None: continue
            if inspect.isclass(attr):
                exp = self.validated.get(pub, set()) if self.external and 'load.py' not in self.path else {m for m in dir(attr) if not m.startswith('_')}
                setattr(proxy, pub, type(pub, (object,), {m: getattr(attr, m) for m in exp if hasattr(attr, m)}))
            else: setattr(proxy, pub, attr)
        return proxy

async def resource(path: str) -> Any:
    cache = container.module_cache(); stack = container.loading_stack()
    if path in cache: return {"data": cache[path], "success": True}
    if path in stack:
        if f"loading:{path}" in sys.modules: return {"data": sys.modules[f"loading:{path}"], "success": True}
        while path in stack: await asyncio.sleep(0.01)
        if path in cache: return {"data": cache[path], "success": True}
    stack.add(path)
    try:
        res = await _internal(path)
        if res.get('success') and res.get('data'):
            async with container.module_cache_lock(): cache[path] = res['data']
        return res
    finally: stack.remove(path)

async def _internal(path: str, raw=False) -> Any:
    try:
        content = await _load_resource(path=path)
        if path.endswith('.json'): return {"data": await convert(content, dict, 'json'), "success": True}
        if path.endswith('.dsl'): return {"data": language.parse_dsl_file(content), "success": True}
        if not path.endswith('.py'): return {"data": content, "success": True}
        unique_name, fake_name = f"mod_{uuid.uuid4().hex[:8]}", f"loading:{path}"
        mod = await _load_py(unique_name, path, content, fake_name)
        if '.test.' in path or raw: return {"data": mod, "success": True}
        ctx = await ValidationContext(path, mod).load(strict=True)
        ctx.resolve(); await ctx.validate(); ctx.compute()
        framework_log("INFO", f"✅ Validated: {path}. Exposed: {list(ctx.allowed)}")
        return {"data": ctx.build(), "success": True}
    except Exception as e:
        framework_log("ERROR", f"❌ Failed to load {path}: {e}"); return {"data": None, "success": False, "errors": [str(e)]}

async def _load_py(name, path, code, placeholder=None):
    module = types.ModuleType(name); module.__file__ = path; sys.modules[name] = module
    if placeholder: sys.modules[placeholder] = module
    for line in code.splitlines():
        if 'imports:' in line:
            try:
                for k, p in (await convert(line.split('imports:')[1].split(';')[0], dict, 'json')).items():
                    r = await resource(p); setattr(module, k, r.get('data'))
            except: pass
            break
    try: exec(code, module.__dict__); return module
    except Exception as e: analyze_exception(e, path, code); raise ImportError(f"Execution failed {path}: {e}")

async def run_dsl_test_suite(ana: Dict, mod: Any) -> Dict:
    suite = ana.get('test_suite', [])
    if not suite: return {'success': True}
    from framework.service.language import DSLVisitor, dsl_functions
    v = DSLVisitor(dsl_functions); v.root_data = ana; res, ok = [], True
    async def resolve(it): return [await resolve(x) for x in it] if isinstance(it, (list, tuple)) else await v.visit(it)
    for i, t in enumerate(suite):
        if not isinstance(t, dict): continue
        target, args, exp = str(t.get('target')), t.get('input_args', ()), t.get('expected_output')
        f = getattr(mod, target, None)
        if not f: ok = False; res.append({'test': i, 'target': target, 'error': 'Missing'}); continue
        try:
            actual = await f(*await resolve(args)) if inspect.iscoroutinefunction(f) else f(*await resolve(args))
            def norm(val): return [norm(x) for x in val] if isinstance(val, (list, tuple)) else val
            if norm(actual) == norm(exp): res.append({'test': i, 'success': True})
            else: ok = False; res.append({'test': i, 'target': target, 'error': f'Exp {exp} got {actual}'})
        except Exception as e: ok = False; res.append({'test': i, 'target': target, 'error': str(e)})
    return {'success': ok, 'results': res}

async def generate_checksum(path: str, save: bool = False, run_tests: bool = True) -> Dict:
    code = await _load_resource(path=path)
    if not code: return {'success': False, 'error': 'Source not found'}
    
    # We use strict=False because the contract might not exist yet
    ctx = await ValidationContext(path).load(strict=False)
    if not ctx.test_code: return {'success': False, 'error': 'No tests found. Contract requires proof of testing.'}
    
    if run_tests:
        framework_log("DEBUG", f"Running tests for contract generation: {path}")
        test_mod = await _load_py("tmp_test_gen", path, code)
        if ctx.is_dsl:
            test_res = await run_dsl_test_suite(ctx.ana, test_mod)
            if not test_res.get('success'):
                framework_log("ERROR", f"Tests failed for {path}: {test_res.get('results')}")
                return {'success': False, 'error': 'DSL Tests failed. Contract aborted.', 'results': test_res}
        framework_log("INFO", f"Tests passed for {path}. Proceeding with contract generation.")
    
    ana, hashes, t_h = analyze_module(code, path), {}, await convert(ctx.test_code, str, 'hash')
    if ctx.is_dsl:
        for pub, priv in ctx.ana.get('exports', {}).items():
            it = ana.get(str(priv), {})
            if it.get('type') in ('function', 'import'):
                l = it['data'].get('lineno', 0); c = estrai_righe_da_codice(code, l, it['data'].get('end_lineno', l))
                hashes.setdefault('__module__', {})[str(pub)] = {'production': await convert(c, str, 'hash'), 'test': t_h}
            elif it.get('type') == 'class':
                for m, d in it['data'].get('methods', {}).items():
                    if not m.startswith('_'): hashes.setdefault(str(pub), {})[m] = {'production': await convert(estrai_righe_da_codice(code, d['lineno'], d['end_lineno']), str, 'hash'), 'test': t_h}
    else:
        for n, d in analyze_module(ctx.test_code, ctx.test_path).items():
            if not isinstance(d, dict) or d.get('type') != 'class': continue
            g = '__module__' if n == 'TestModule' else n.replace('Test','')
            for m, md in d['data'].get('methods', {}).items():
                if not m.startswith('test_'): continue
                raw = m.replace('test_',''); info = (ana.get(raw) if g == '__module__' else ana.get(g,{}).get('data',{}).get('methods',{}).get(raw,{}))
                if info: hashes.setdefault(g, {})[raw] = {'production': await convert(estrai_righe_da_codice(code, info.get('lineno',0), info.get('end_lineno',0)), str, 'hash'), 'test': await convert(estrai_righe_da_codice(ctx.test_code, md['lineno'], md['end_lineno']), str, 'hash')}
    if save and hashes: await backend(path=ctx.contract_json, content=json.dumps(hashes, indent=4), mode='w')
    return {'data': {path: hashes}, 'success': True}

async def register(**cfg: Any) -> Dict:
    path, name = cfg.get('path'), cfg.get('service', cfg.get('name'))
    payload, keys = cfg.get('payload', cfg.get('config', {})), cfg.get('dependency_keys')
    async def _task(c=None):
        mod = (await resource(path)).get('data'); attr = getattr(mod, cfg.get('adapter', name))
        if not hasattr(container, name): setattr(container, name, providers.Singleton(list))
        if keys: setattr(container, name, providers.Factory(attr, **payload, providers={k: getattr(container, k)() for k in keys if hasattr(container, k)}))
        else: getattr(container, name)().append(attr(config=payload))
        return {"success": True}
    return await flow.pipe(flow.step(_task), context=cfg)
async def bootstrap(): return await resource("framework/service/bootstrap.dsl")