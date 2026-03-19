"""
DSL Language Interpreter
"""

import asyncio
import inspect
import operator

from lark import Lark, Transformer, Token, v_args
from dataclasses import dataclass, field

import framework.service.scheme as scheme
import framework.service.flow as flow
import framework.service.load as load

import random

# ── Grammar ───────────────────────────────────────────────────────────────────

GRAMMAR = r"""
start: dictionary | [item (item)*] -> dictionary_node

dictionary: "{" [item (item)*] "}" -> dictionary_node

item: (pair|type_sequence) ASSIGN_OP sequence ";"? 
    | (atom|sequence) COLON_OP sequence ";"?
    | function_call _ARROW sequence ";"? -> task

?type_sequence: pair ("," pair)* ","? -> sequence
?sequence: expr ("," expr)* ","?

?expr: pipe
?pipe: logic
     | logic (PIPE logic)+ -> pipe_node

?logic: comparison
      | "not" logic                -> not_op
      | logic ("and" | "&") logic  -> and_op
      | logic ("or"  | "|") logic  -> or_op

?comparison: sum
           | comparison COMPARISON_OP sum -> binary_op

?sum: term
    | sum ARITHMETIC_OP term -> binary_op

?term: power
     | term "*" power -> binary_op
     | term "/" power -> binary_op
     | term "%" power -> binary_op

?power: atom | atom "^" power -> power

?atom.7: value
     | identifier
     | tuple
     | list
     | dictionary
     | function_call
     | function_value

?tuple: "(" [sequence] ")" -> tuple_node | "(" [type_sequence] ")" -> tuple_node
pair.6: atom ":" atom
?list: "[" [sequence] "]" -> list_node

function_call: identifier "(" [sequence|type_sequence] ")"
function_value.10: tuple dictionary tuple

identifier: CNAME -> identifier
| QUALIFIED_CNAME -> identifier
| "@" CNAME -> context_var
| "@" QUALIFIED_CNAME -> context_var

value: SIGNED_NUMBER      -> number
     | STRING             -> string
     | "true"i            -> true
     | "false"i           -> false
     | "none"i            -> any_val

PIPE: "|>"
_ARROW: "->"
ASSIGN_OP: ":="
COLON_OP: ":"
COMPARISON_OP: "==" | "!=" | ">=" | "<=" | ">" | "<"
ARITHMETIC_OP: "+" | "-" | "*" | "/" | "%"
STRING: ESCAPED_STRING | SINGLE_QUOTED_STRING
SINGLE_QUOTED_STRING: /'[^']*'/
FILTER_PATTERN: "*[" CNAME "=" STRING "]"
QUALIFIED_CNAME: CNAME ("." (CNAME|INT|FILTER_PATTERN|"*"))+
INT : /[0-9]+/

%import common.SIGNED_NUMBER
%import common.ESCAPED_STRING
%import common.CNAME
%import common.WS
%ignore WS

COMMENT: /\/\/[^\n]*/ | /\/\*[\s\S]*?\*\//
%ignore COMMENT
"""

# ── Types ─────────────────────────────────────────────────────────────────────

TYPE_MAP = {
    'natural': int, 'integer': int, 'real': float, 'rational': float,
    'boolean': bool, 'complex': complex, 'matrix': list, 'vector': list, 'set': set,
    'int': int, 'i8': int, 'i16': int, 'i32': int, 'i64': int,
    'n8': int, 'n16': int, 'n32': int, 'n64': int,
    'f32': float, 'f64': float, 'str': str, 'bool': bool,
    'dict': dict, 'list': list, 'any': object, 'type': dict,
    'tuple': tuple, 'function': tuple,
}

CUSTOM_TYPES = {}

DSL_FUNCTIONS = {
    'random': random.randint,
    'resource': load.resource,
    'transform': scheme.transform,
    'get': scheme.get,
    'normalize': scheme.normalize,
    'put': scheme.put,
    'format': scheme.format,
    'convert': scheme.convert,
    'keys':   lambda d: list(d.keys()) if isinstance(d, dict) else [],
    'values': lambda d: list(d.values()) if isinstance(d, dict) else [],
    'union':  lambda a, b: {**a, **b},
    'print':  lambda *inputs: (print(*inputs), inputs)[1],
    'pass':   lambda *inputs: inputs,
} | TYPE_MAP | {'extension': 'py'}

# ── Ops ───────────────────────────────────────────────────────────────────────

OPS = {
    '+': operator.add,  '-': operator.sub,  '*': operator.mul,
    '/': operator.truediv, '%': operator.mod, '^': operator.pow,
    '==': operator.eq,  '!=': operator.ne,
    '>':  operator.gt,  '<':  operator.lt,
    '>=': operator.ge,  '<=': operator.le,
    'and': lambda a, b: a and b,
    'or':  lambda a, b: a or b,
}

# ── Transformer ───────────────────────────────────────────────────────────────

@v_args(meta=True)
class DSLTransformer(Transformer):

    def task(self, meta, items):
        # items may contain trigger, deps (list), and action
        # _ARROW is ignored because of the _ prefix in grammar
        items = [i for i in items if i is not None]
        trigger = items[0]
        action = items[1]

        return self._m({"type": "task", "trigger": trigger, "action": action}, meta)

    def _m(self, node, meta):
        node["meta"] = {"line": meta.line, "column": meta.column,
                        "end_line": meta.end_line, "end_column": meta.end_column} \
                       if hasattr(meta, "line") else \
                       {"line": None, "column": None, "end_line": None, "end_column": None}
        return node

    def number(self, meta, n):
        v = str(n[0]); return self._m({"type":"number","value":float(v) if "." in v else int(v)}, meta)

    def string(self, meta, s):
        return self._m({"type":"string","value":str(s[0])[1:-1]}, meta)

    def true(self, meta, _):    return self._m({"type":"bool","value":True},  meta)
    def false(self, meta, _):   return self._m({"type":"bool","value":False}, meta)
    def any_val(self, meta, _): return self._m({"type":"any"}, meta)

    def identifier(self, meta, s):
        return self._m({"type":"var","name":str(s[0])}, meta)

    def context_var(self, meta, s):
        return self._m({"type":"context_var","name":str(s[0])}, meta)

    def function_value(self, meta, a):
        return self._m({"type":"function_def","params":a[0],"body":a[1],"return_type":a[2]}, meta)

    def sequence(self, meta, items):
        return self._m({"type":"sequence","items":[i for i in items if i is not None]}, meta)

    def _unwrap(self, meta, items, typ):
        items = [i for i in items if i is not None]
        if len(items) == 1 and isinstance(items[0], dict) and items[0].get("type") == "sequence":
            items = items[0]["items"]
        return self._m({"type": typ, "items": items}, meta)

    def tuple_node(self, meta, items): return self._unwrap(meta, items, "tuple")
    def list_node(self, meta, items):  return self._unwrap(meta, items, "list")

    def dictionary_node(self, meta, items):
        return self._m({"type":"dict","items":[i for i in items if i is not None]}, meta)

    def pair(self, meta, a):
        return self._m({"type":"pair","key":a[0],"value":a[1]}, meta)

    def item(self, meta, tree):
        left, sep, right = tree[0], str(tree[1]), tree[2]
        if sep == ":=":
            return self._m({"type":"declaration","target":left,"value":right}, meta)
        return self._m({"type":"pair","key":left,"value":right}, meta)

    def function_call(self, meta, tree):
        fn = tree[0]
        inputs = tree[1].get("items",[]) if isinstance(tree[1],dict) and tree[1]["type"] == "sequence" else [tree[1]]
        args, kwargs = [], {}
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("type") == "pair":
                kwargs[inp["key"]["name"]] = inp["value"]
            else:
                args.append(inp)
        return self._m({"type":"call","name":fn.get("name"),"args":args,"kwargs":kwargs}, meta)

    def binary_op(self, meta, a):
        if len(a) == 2:
            return self._m({"type":"binop","op":"*","left":a[0],"right":a[1]}, meta)
        return self._m({"type":"binop","op":str(a[1]),"left":a[0],"right":a[2]}, meta)

    def power(self, meta, a):
        return self._m({"type":"binop","op":"^","left":a[0],"right":a[1]}, meta)

    def not_op(self, meta, a):  return self._m({"type":"not","value":a[0]}, meta)
    def and_op(self, meta, a):  return self._m({"type":"binop","op":"and","left":a[0],"right":a[1]}, meta)
    def or_op(self, meta, a):   return self._m({"type":"binop","op":"or", "left":a[0],"right":a[1]}, meta)

    def pipe_node(self, meta, items):
        return self._m({"type":"pipe","steps":[i for i in items if not isinstance(i, Token)]}, meta)

    def start(self, meta, items): return items[0]

# ── Runtime helpers ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LazyBinOp:
    fn: callable = field(repr=False, compare=False)
    description: str
    def __call__(self, *a, **kw): return self.fn(*a, **kw)
    def __repr__(self):           return self.description

@dataclass(frozen=True)
class ContextVar:
    name: str
    def __call__(self, *_, **ctx): return scheme.get(ctx, self.name)
    def __repr__(self):            return self.name

class DSLRuntimeError(Exception):
    def __init__(self, message, meta=None):
        if meta:
            sl, sc, el, ec = meta.get("line"), meta.get("column"), meta.get("end_line"), meta.get("end_column")
            if sl is not None:
                loc = f"line {sl}:{sc} - {el}:{ec}" if el else f"line {sl}, col {sc}"
                message += f" ({loc})"
        super().__init__(message)

# ── Interpreter ───────────────────────────────────────────────────────────────
#
# visit_dict usa due path distinti:
#   • fast-path  — dict senza dipendenze interne (la maggioranza: schema, mapper,
#                  config, record). Valutazione sequenziale, zero overhead DAG.
#   • slow-path  — dict dove almeno una chiave dipende da un'altra chiave dello
#                  stesso dict. Attiva flow.run_ast con ordinamento topologico.
#
# Il top-level del file DSL (dictionary_node radice) passa sempre dal slow-path
# perché le dichiarazioni `:=` si referenziano tra loro per definizione.
#
# Per dict reattivi (scheduled / event-driven), introdurre un costrutto
# esplicito `reactive:` che bypassa visit_dict e usa flow.run direttamente.

class Interpreter:

    def __init__(self): 
        self._stack = []
        self._tasks = []
        self.runner = flow.DagRunner()

    # ── visita generica ───────────────────────────────────────────────────────

    async def visit(self, node, env, gad=[]):
        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)
        if not method:
            raise DSLRuntimeError(f"Tipo AST sconosciuto: '{t}'", node.get("meta"))
        self._stack.append(node)
        try:
            return await method(node, env, gad)
        except DSLRuntimeError as e:
            trace = " -> ".join(
                f"{n['type']}({n.get('meta',{}).get('line','?')}:{n.get('meta',{}).get('column','?')})"
                for n in self._stack)
            e.args = (f"{e.args[0]} | Stack: {trace}",); raise
        finally:
            self._stack.pop()

    # ── primitivi ─────────────────────────────────────────────────────────────

    async def visit_number(self, n, e, gad):      return n["value"], e, gad
    async def visit_string(self, n, e, gad):      return n["value"], e, gad
    async def visit_bool(self, n, e, gad):        return n["value"], e, gad
    async def visit_any(self, n, e, gad):         return None, e, gad
    async def visit_identifier(self, n, e, gad):  return n["name"], e, gad
    async def visit_var(self, n, e, gad):         return scheme.get(e, n["name"], n["name"]), e, gad
    async def visit_context_var(self, n, e, gad): return ContextVar(n["name"]), e, gad

    async def visit_function_def(self, n, e, gad):
        p = n["params"].get("items", [n["params"]])
        r = n["return_type"].get("items", [n["return_type"]])
        return (p, n["body"], r), e, gad

    # ── strutture ─────────────────────────────────────────────────────────────

    async def visit_task(self, node, env, gad=[]):
        kwargs = {}
        for k, v in node['trigger'].get("kwargs", {}).items():
            val, env, gad = await self.visit(v, env, gad)
            kwargs[k] = val
        self._tasks.append({
            "name": node['trigger']['name'],
            "action": node['action'],
            "kwargs": kwargs
        })
        
        return (node['trigger']['name'], node['action']), env, gad
        

    async def _collect(self, node, env, cast, gad=[]):
        items = []
        for item in node["items"]:
            val, env, gad = await self.visit(item, env, gad)
            items.append(val)
        return cast(items), env, gad

    async def visit_tuple(self, n, e, gad=[]):    return await self._collect(n, e, tuple, gad)
    async def visit_sequence(self, n, e, gad=[]): return await self._collect(n, e, tuple, gad)
    async def visit_list(self, n, e, gad=[]):     return await self._collect(n, e, list, gad)

    async def visit_pair(self, node, env, gad=[]):
        value, _, gad = await self.visit(node["value"], env, gad)
        key = node["key"]["name"] if node["key"]["type"] == "var" \
              else (await self.visit(node["key"], env))[0]
        return (key, value), env, gad

    async def visit_declaration(self, node, env, gad=[]):
        val, _, gad = await self.visit(node["value"], env, gad)
        key, _, gad = await self.visit(node["target"], env, gad)
        meta   = node.get("meta")
        items  = key if isinstance(key[0], tuple) else [key]
        if node["target"]["type"] == "pair":
            tipo, name = node["target"]["key"]["name"], node["target"]["value"]["name"]
            if tipo == "type": CUSTOM_TYPES[name] = val; return (name, val), env, gad
            return (name, await self._check(val, tipo, meta, name)), env, gad
        keys, values = [], []
        for i, _ in enumerate(items):
            tipo = node["target"]["items"][i]["key"]["name"]
            name = node["target"]["items"][i]["value"]["name"]
            if tipo == "type": CUSTOM_TYPES[name] = val
            keys.append(name)
            values.append(await self._check(val[i] if isinstance(val, tuple) else val, tipo, meta, name))
        return (tuple(keys), tuple(values)), env, gad

    # ── dict ─────────────────────────────────────────────────────────────────

    async def visit_dict(self, node, env, gad=[]):
        items = node["items"]
        result = {}
        for it in items:
            (key, val), _, gad = await self.visit(it, env|result, gad)
            if isinstance(key, tuple):
                result.update(dict(zip(key, val)))
            else:
                result[key] = val
                gad.append(flow.node(key, lambda x:val))
        return result, env, gad

    async def visit_pipe(self, node, env, gad=[]):
        steps = node["steps"]
        val, env, gad = await self.visit(steps[0], env, gad)
        for step in steps[1:]:
            val, env, gad = await self.visit_call(step, env, gad, args=[val])
        return val, env, gad
        '''steps = node["steps"]
        val, _ = await self.visit(steps[0], env)
        
        def make_stage(ast_node):
            async def stage(input_data):
                res, _ = await self.visit_call(ast_node, env, args=[flow.value_of(input_data)])
                return res
            return stage

        stages = [make_stage(s) for s in steps[1:]]
        if not stages: return val, env

        # Costruiamo il nodo pipeline e lo eseguiamo via flow.run
        pipe_node = flow.pipeline("pipe_execution", stages)
        _, results = await flow.run([pipe_node], {"kwargs": val})
        
        return flow.value_of(results["pipe_execution"]), env'''

    async def visit_binop(self, node, env, gad=[]):
        left,  env, gad = await self.visit(node["left"],  env, gad)
        right, env, gad = await self.visit(node["right"], env, gad)
        '''left_res,  env = await self.visit(node["left"],  env)
        right_res, env = await self.visit(node["right"], env)
        left, right = flow.value_of(left_res), flow.value_of(right_res)'''
        op = node["op"]
        if isinstance(left,  tuple): left  = left[0]
        if isinstance(right, tuple): right = right[0]
        if callable(left) or callable(right):
            fn_op = OPS[op]
            def lazy(*_, **ctx):
                l = left(**ctx)  if callable(left)  else left
                r = right(**ctx) if callable(right) else right
                return fn_op(l, r)
            return LazyBinOp(lazy, f"{left!r} {op} {right!r}"), env, gad
        try:
            return OPS[op](left, right), env, gad
        except Exception as e:
            raise DSLRuntimeError(f"Errore '{op}': {e}", node.get("meta"))

    async def visit_not(self, node, env, gad=[]):
        val, env, gad = await self.visit(node["value"], env, gad)
        return not val, env, gad

    # ── chiamate a funzione ───────────────────────────────────────────────────

    async def visit_call(self, node, env, gad=[], args=(), kwargs=None):
        name, meta = node.get("name"), node.get("meta")
        ast_args   = [(await self.visit(a, env))[0] for a in node.get("args", [])]
        ast_kwargs = {k: (await self.visit(v, env))[0] for k, v in node.get("kwargs", {}).items()}
        all_args   = list(args) + ast_args
        all_kwargs = {**(kwargs or {}), **ast_kwargs}
        '''ast_args   = [flow.value_of((await self.visit(a, env))[0]) for a in node.get("args", [])]
        ast_kwargs = {k: flow.value_of((await self.visit(v, env))[0]) for k, v in node.get("kwargs", {}).items()}
        all_args   = [flow.value_of(a) for a in args] + ast_args
        all_kwargs = {k: flow.value_of(v) for k, v in {**(kwargs or {}), **ast_kwargs}.items()}'''
        fn = scheme.get(env, str(name))
        if callable(fn):
            result = await fn(*all_args, **all_kwargs) \
                     if asyncio.iscoroutinefunction(fn) else fn(*all_args, **all_kwargs)
        elif isinstance(fn, tuple) and len(fn) == 3:
            result = await self._call_dsl_fn(fn, all_args, all_kwargs)
        else:
            raise DSLRuntimeError(f"Funzione sconosciuta: '{name}'", meta)
        return result, env, gad

    async def _call_dsl_fn(self, fn_triple, args, kwargs):
        params_ast, body_ast, return_ast = fn_triple
        local_env = {}
        for p, a in zip(params_ast, args):
            local_env[p["value"]["name"]] = await self._check(
                a, p["key"]["name"], p.get("meta"), p["value"]["name"])
        result, _, _ = await self.visit(body_ast, local_env)
        out = []
        for ty in return_ast:
            (tipo, name), _, _ = await self.visit(ty, local_env)
            if name in result:
                out.append(await self._check(result[name], tipo, ty.get("meta"), name))
        return out[0] if len(out) == 1 else out

    async def invoke(self, fn, args=(), kwargs=None):
        """Esegue una funzione dall'esterno (usato dal tester)."""
        if callable(fn):
            s = flow.step(fn, *args, **(kwargs or {}))
        elif isinstance(fn, tuple) and len(fn) == 3:
            s = flow.step(self._call_dsl_fn, fn, args, kwargs or {})
        else:
            raise DSLRuntimeError("Funzione sconosciuta")
        return await flow.act(s)

    async def _check(self, value, expected, meta, name):
        if expected in CUSTOM_TYPES:
            return await scheme.normalize(value, CUSTOM_TYPES[expected])
        py = TYPE_MAP.get(expected)
        if py and not (isinstance(value, py) and not (py is int and isinstance(value, bool))):
            raise DSLRuntimeError(
                f"Tipo errato '{name}': atteso {expected}, ottenuto {type(value).__name__}", meta)
        return value

    # ── Orchestrazione task via flow.run() ─────────────────────────────────────
 
    async def _build_flow_nodes(self, env):
        """
        Converte i task DSL in nodi flow.node().
        
        Ogni task diventa un nodo con:
          - name: task_name
          - fn: funzione che visita action_ast
          - deps: lista di dipendenze
          - params: metadati (every, on, etc.)
        """
        flow_nodes = []
        interpreter = self
        
        for task in self._tasks:
            task_name = task["name"]
            action_ast = task["action"]
            deps = [a["name"] for a in action_ast["args"] if a["type"] == "var"]
            #print("###############################DEPS",deps)
            kwargs = task.get("kwargs", {})
            #kwargs['deps'] = deps + kwargs.get('deps', [])
            
            # Crea una closure che cattura correttamente le variabili
            def make_task_fn(ast, interpreter_ref, environment):
                async def task_fn(env_dict):
                    try:
                        #print("###############################AST",ast)
                        call = env_dict.get(ast["name"])
                        #print("###############################CALL",ast["name"],call)
                        args = [(await self.visit(a, env_dict))[0] for a in ast["args"]]
                        #print("###############################ARGS",args)
                        
                        kwargs = {k: env_dict.get(v["name"]) for k, v in ast["kwargs"].items()}
                        #print("###############################KWARGS",kwargs)

                        #call, _, _ = await interpreter_ref.visit(ast, environment)
                        result = await interpreter_ref.invoke(call,args,kwargs)
                        result = result.get("outputs",result)
                        #print(f"\n\n####RESULT {task_name}:{ast['name']}({', '.join(map(str,args))},{', '.join([f'{k}:{v}' for k, v in kwargs.items()])})={result}")
                        return result
                    except Exception as e:
                        return flow.error(str(e))
                return task_fn
            
            task_fn = make_task_fn(action_ast, interpreter, env)
            
            # Crea il nodo flow
            node = flow.node(name=task_name,fn=task_fn,**kwargs)
            
            flow_nodes.append(node)
        
        return flow_nodes
 
    # ── entry point ───────────────────────────────────────────────────────────
    async def start(self):
        await self.runner.start()

    async def stop(self):
        await self.runner.stop()

    async def run(self, name, ast, env={}):
        self._tasks = [] # Reset tasks for this run
        self._stack = []
        result , _ , gad = await self.visit(ast, env)
        flow_nodes = await self._build_flow_nodes(env|result)
        await self.runner.add_file(name,flow_nodes, env|result)
        #await self.runner.wait_file(name)
        #ctx = self.runner.get_file_context(name)
        #print("###############################4",ctx)
        return result
 


# ── Public API ────────────────────────────────────────────────────────────────

def create_parser():
    return Lark(GRAMMAR, parser='lalr', propagate_positions=True)

def parse(source: str, parser: Lark) -> dict:
    return DSLTransformer().transform(parser.parse(source))

async def execute(source_or_ast, parser, functions):
    ast = parse(source_or_ast, parser) if isinstance(source_or_ast, str) else source_or_ast
    return await Interpreter().run(ast, env=functions)