"""
DSL Language Interpreter
"""

import asyncio
import inspect
import operator

from lark import Lark, Transformer, Token, v_args
from dataclasses import dataclass, field
from collections import ChainMap

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
      | ("not" | "!") logic        -> not_op
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
    #'resource': load.resource,
    'foreach': flow.foreach,
    'switch':  flow.switch,
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
        lazy = fn.get("type") == "context_var"
        inputs = tree[1].get("items",[]) if isinstance(tree[1],dict) and tree[1]["type"] == "sequence" else [tree[1]]
        args, kwargs = [], {}
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("type") == "pair":
                kwargs[inp["key"]["name"]] = inp["value"]
            else:
                args.append(inp)

        node = {"type":"call","name":fn.get("name"),"args":args,"kwargs":kwargs}
        if lazy: node["lazy"] = True
        return self._m(node, meta)

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

@dataclass(frozen=True)
class LazyCall:
    interpreter: object = field(repr=False, compare=False)
    name: str
    call_node: dict = field(repr=False, compare=False)
    env: dict = field(repr=False, compare=False)
    '''def __call__(self, env, *args, **kwargs):
        return self.interpreter.visit_call(self.call_node, env, *args, **kwargs)'''
    def __call__(self, env, *args, **kwargs):
        tt = {**self.call_node, "lazy": False}
        return self.interpreter.visit_call(tt, self.env|env, *args, **kwargs)
    def __repr__(self): return f"@{self.name}(...)"

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
        self._dag = []
        self.runner = flow.DagRunner()

    # ── visita generica ───────────────────────────────────────────────────────

    async def visit(self, node, env,path=""):
        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)
        if not method:
            raise DSLRuntimeError(f"Tipo AST sconosciuto: '{t}'", node.get("meta"))
        self._stack.append(node)
        try:
            return await method(node, env,path)
        except DSLRuntimeError as e:
            trace = " -> ".join(
                f"{n['type']}({n.get('meta',{}).get('line','?')}:{n.get('meta',{}).get('column','?')})"
                for n in self._stack)
            e.args = (f"{e.args[0]} | Stack: {trace}",); raise
        finally:
            self._stack.pop()

    def _resolve_scope(self, path, name, available):
        """
        Risolve il nome cercando prima nello scope locale (più profondo),
        poi risalendo verso la radice. Restituisce il path completo se trovato,
        altrimenti il nome grezzo.
        
        es: path="a.b.c", name="x", available={"a.b.x","x"} → "a.b.x"
        """
        parts = path.split(".")
        # Scende dal più specifico al più generale
        for i in range(len(parts), -1, -1):
            candidate = ".".join(parts[:i] + [name]) if i > 0 else name
            if candidate in available:
                return candidate
        # Fallback: cerca per suffisso (es. "x" matcha "a.b.x")
        for avail in sorted(available, key=len, reverse=True):
            if avail == name or avail.endswith(f".{name}"):
                return avail
        return name

    def _find_vars(self, node, _seen=None):
        """Visita ricorsivamente l'AST raccogliendo tutte le var/context_var."""
        if _seen is None:
            _seen = set()
        if isinstance(node, dict):
            t = node.get("type")
            if t in ("var", "context_var"):
                return {node["name"]}
            # Non scendere dentro function_def (scope separato)
            if t == "function_def":
                return set()
            return {
                v for key, child in node.items()
                if key != "meta"
                for v in self._find_vars(child, _seen)
            }
        if isinstance(node, (list, tuple)):
            return {v for child in node for v in self._find_vars(child, _seen)}
        return set()

    def _register_task(self, node, env, path=None):
        """Registra un nodo AST come task reattivo nel grafo (Auto-Tasking)."""
        if "session_id" in env: return # Già in esecuzione
        meta = node.get("meta", {})
        name = self._node_name(node)
        if any(t["name"] == name for t in self._tasks): return
        self._tasks.append({"name": name, "action": node, "kwargs": {}, "path": path or name})

    def _node_name(self, node):
        meta = node.get("meta", {})
        return f"pipe_L{meta.get('line','?')}C{meta.get('column','?')}"

    # ── primitivi ─────────────────────────────────────────────────────────────

    async def visit_number(self, n, e, path=""):      return n["value"], e
    async def visit_string(self, n, e, path=""):      return n["value"], e
    async def visit_bool(self, n, e, path=""):        return n["value"], e
    async def visit_any(self, n, e, path=""):         return None, e
    async def visit_identifier(self, n, e, path=""):  return n["name"], e
    async def visit_var(self, n, e, path=""):         return scheme.get(e, n["name"], n["name"]), e
    async def visit_context_var(self, n, e, path=""): return ContextVar(n["name"]), e

    async def visit_function_def(self, n, e, path=""):
        p = n["params"].get("items", [n["params"]])
        r = n["return_type"].get("items", [n["return_type"]])
        return (p, n["body"], r, path), e

    # ── strutture ─────────────────────────────────────────────────────────────

    async def visit_task(self, node, env, path=""):
        task_name = node['trigger']['name']
        task_path = f"{path}.{task_name}" if path else task_name
        kwargs = {}
        for k, v in node['trigger'].get("kwargs", {}).items():
            val, env = await self.visit(v, env, path=task_path + "." + k)
            kwargs[k] = val
        self._tasks.append({
            "name": task_name,
            "action": node['action'],
            "kwargs": kwargs,
            "path": task_path
        })
        
        return (task_name, node['action']), env
        

    async def _collect(self, node, env, cast, path=""):
        items = []
        for i, item in enumerate(node["items"]):
            item_path = f"{path}[{i}]" if path else f"[{i}]"
            val, env = await self.visit(item, env, path=item_path)
            items.append(val)
        return cast(items), env

    async def visit_tuple(self, n, e, path=""):    return await self._collect(n, e, tuple, path=path)
    async def visit_sequence(self, n, e, path=""): return await self._collect(n, e, tuple, path=path)
    async def visit_list(self, n, e, path=""):     return await self._collect(n, e, list, path=path)

    async def visit_pair(self, node, env, path=""):
        if node["key"]["type"] == "var":
            key = node["key"]["name"]
        else:
            key, _ = await self.visit(node["key"], env, path=path + ".key")
            key = key[0] if isinstance(key, tuple) else key
        
        val_path = f"{path}.{key}" if path else str(key)
        value, _ = await self.visit(node["value"], env, path=val_path)
        return (key, value), env

    async def visit_declaration(self, node, env, path=""):
        # We need the key first to build the path for the value
        target = node["target"]
        if target["type"] == "pair":
             target_name = target["value"]["name"]
        elif target["type"] == "var":
             target_name = target["name"]
        else:
             target_name = None # For complex / tuple destructuring
             
        val_path = f"{path}.{target_name}" if path and target_name else (target_name or path)
        val, _ = await self.visit(node["value"], env, path=val_path)
        key, _ = await self.visit(node["target"], env, path=path)
        meta   = node.get("meta")
        items  = key if isinstance(key[0], tuple) else [key]
        if node["target"]["type"] == "pair":
            tipo, name = node["target"]["key"]["name"], node["target"]["value"]["name"]
            if tipo == "type": CUSTOM_TYPES[name] = val; return (name, val), env
            return (name, await self._check(val, tipo, meta, name, path=val_path)), env
        keys, values = [], []
        for i, _ in enumerate(items):
            tipo = node["target"]["items"][i]["key"]["name"]
            name = node["target"]["items"][i]["value"]["name"]
            if tipo == "type": CUSTOM_TYPES[name] = val
            keys.append(name)
            item_val_path = f"{val_path}[{i}]" if val_path else f"[{i}]"
            values.append(await self._check(val[i] if isinstance(val, tuple) else val, tipo, meta, name, path=item_val_path))
        return (tuple(keys), tuple(values)), env

    # ── dict ─────────────────────────────────────────────────────────────────

    async def visit_dict(self, node, env,path=""):
        items = node["items"]
        result = {}
        for it in items:
            (key, val), _ = await self.visit(it, env|result,path=path)
            if isinstance(key, tuple):
                result.update(dict(zip(key, val)))
            else:
                result[key] = val
        return result, env

    async def visit_pipe(self, node, env, path=""):
        steps = node["steps"]
        val, env = await self.visit(steps[0], env, path)
        for step in steps[1:]:
            val, env = await self.visit_call(step, env, path, args=[val])
        return val, env

    async def visit_binop(self, node, env, path=""):
        left_path = path + ".left" if path else "left"
        right_path = path + ".right" if path else "right"
        left,  env = await self.visit(node["left"],  env, path=left_path)
        right, env = await self.visit(node["right"], env, path=right_path)
        op = node["op"]
        if isinstance(left,  tuple): left  = left[0]
        if isinstance(right, tuple): right = right[0]
        if callable(left) or callable(right):
            fn_op = OPS[op]
            def lazy(*_, **ctx):
                l = left(**ctx)  if callable(left)  else left
                r = right(**ctx) if callable(right) else right
                return fn_op(l, r)
            return LazyBinOp(lazy, f"{left!r} {op} {right!r}"), env
        try:
            return OPS[op](left, right), env
        except Exception as e:
            raise DSLRuntimeError(f"Errore '{op}': {e} at {path}", node.get("meta"))

    async def visit_not(self, node, env, path=""):
        val, env = await self.visit(node["value"], env, path=path + ".not")
        if callable(val):
            def lazy(*_, **ctx):
                return not val(**ctx)
            return LazyBinOp(lazy, f"not {val!r}"), env
        return not val, env

    # ── chiamate a funzione ───────────────────────────────────────────────────

    async def visit_call(self, node, env, path="", args=(), kwargs=None):
        name, meta = node.get("name"), node.get("meta")
        if node.get("lazy"):
            #node.pop("lazy", None)
            return LazyCall(self,name, node, env), env
        call_path  = f"{path}.{name}" if path else str(name)
        ast_args   = [(await self.visit(a, env, path=f"{call_path}[{i}]"))[0] for i, a in enumerate(node.get("args", []))]
        ast_kwargs = {k: (await self.visit(v, env, path=f"{call_path}.{k}"))[0] for k, v in node.get("kwargs", {}).items()}
        all_args   = list(args) + ast_args
        all_kwargs = {**(kwargs or {}), **ast_kwargs}
        fn = scheme.get(env, str(name))
        
        # Utilizziamo self.invoke (che gestisce sia Python callables che DSL functions)
        res = await self.invoke(fn, all_args, all_kwargs or {}, path=call_path)
        if not res["success"]:
            raise DSLRuntimeError(f"Errore call '{name}': {res['errors']}", meta)
            
        return res["outputs"], env

    async def _call_dsl_fn(self, fn_triple, args, kwargs, path=""):
        params_ast, body_ast, return_ast = fn_triple[:3]
        local_env = {}
        for i, (p, a) in enumerate(zip(params_ast, args)):
             name = p["value"]["name"]
             arg_path = f"{path}[{i}]" if path else name
             local_env[name] = await self._check(a, p["key"]["name"], p.get("meta"), name, path=arg_path)

        for p in params_ast[len(args):]:
            name = p["value"]["name"]
            if name in kwargs:
                arg_path = f"{path}.{name}" if path else name
                local_env[name] = await self._check(kwargs[name], p["key"]["name"], p.get("meta"), name, path=arg_path)
        
        result, _ = await self.visit(body_ast, local_env, path=path + "->body")
        out = []
        for i, ty in enumerate(return_ast):
            (tipo, name), _ = await self.visit(ty, local_env, path=path + f"->out[{i}]")
            if name in result:
                out_path = f"{path}->out.{name}"
                out.append(await self._check(result[name], tipo, ty.get("meta"), name, path=out_path))
        return out[0] if len(out) == 1 else out

    async def invoke(self, fn, args=(), kwargs={}, path=""):
        """Esegue una funzione dall'esterno (usato dal tester)."""
        if isinstance(fn, LazyCall):
            merged = ChainMap(kwargs, fn.env)
            res, _ = await self.visit_call(fn.call_node, merged, path=path)
            return res
        elif callable(fn):
            s = flow.step(fn, *args, **kwargs)
        elif isinstance(fn, tuple) and (len(fn) == 3 or len(fn) == 4):
            s = flow.step(self._call_dsl_fn, fn, args, kwargs, path)
        else:
            raise DSLRuntimeError(f"{fn} Funzione sconosciuta")
        return await flow.act(s)

    async def _check(self, value, expected, meta, name, path=""):
        if expected in CUSTOM_TYPES:
            return await scheme.normalize(value, CUSTOM_TYPES[expected])
        py = TYPE_MAP.get(expected)
        if py and not (isinstance(value, py) and not (py is int and isinstance(value, bool))):
            display_name = path if path else name
            raise DSLRuntimeError(
                f"Tipo errato '{display_name}': atteso {expected}, ottenuto {type(value).__name__}", meta)
        return value

    # ── Orchestrazione task via flow.run() ─────────────────────────────────────
 
    async def _build_flow_nodes(self, env):
        flow_nodes, interpreter = [], self
        available = {t["path"] for t in self._tasks}

        for task in self._tasks:
            name = task.get("name")
            t_path, action = task.get("path", name), task["action"]
            kw = task.get("kwargs", {})
            
            # Estrazione sicura e ricorsiva di tutte le dipendenze (incluse quelle nelle pipe)
            raw_deps = self._find_vars(action) | self._find_vars(kw)
            deps = {self._resolve_scope(t_path, d, available) for d in raw_deps}
            if name in deps:
                deps.remove(name)
            kw['deps'] = list(deps)
            
            def make_task_fn(ast, interpreter_ref, t_path):
                if ast.get("type") == "pipe":
                    async def task_fn(env_dict):
                        try:
                            return await interpreter_ref.visit(ast, env_dict, path=t_path)
                        except Exception as e:
                            return flow.error(str(e))
                elif ast.get("type") == "call":
                    async def task_fn(env_dict):
                        try:
                            call = scheme.get(env_dict, ast["name"])
                            args = [(await interpreter_ref.visit(a, env_dict, path=t_path+".args"))[0] for a in ast.get("args",[])]
                            kwargs = {k: (await interpreter_ref.visit(v, env_dict, path=t_path+"."+k))[0] for k, v in ast.get("kwargs",{}).items()}
                            res = await interpreter_ref.invoke(call, args, kwargs, path=t_path)
                            return res.get("outputs", res)
                        except Exception as e: return flow.error(str(e))
                else:
                    async def task_fn(env_dict):
                        # Altrimenti visitiamo l'intero nodo (es. pipe, binop, lambda)
                        call, _ = await interpreter_ref.visit(ast, env_dict, path=t_path)
                        # Se il risultato è già un valore (non chiamabile), è il nostro output
                        #print(call)
                        if not callable(call):
                            res = flow.success(call)
                        else:
                            res = await interpreter_ref.invoke(call, [], {}, path=t_path)
                        return res.get("outputs", res)
                return task_fn
            
            flow_nodes.append(flow.node(name=t_path, fn=make_task_fn(action, interpreter, t_path), path=t_path, **kw))
        return flow_nodes
 
    # ── entry point ───────────────────────────────────────────────────────────
    async def start(self):
        await self.runner.start()
        #await self.runner.add_file('interpreter', [])
        #self.runner.create_session('interpreter', 'interpreter', {})

    async def stop(self):
        await self.runner.stop()

    async def run(self, name, ast, session, env={}):
        self._tasks = [] # Reset tasks for this run
        self._stack = []
        self._dag = []
        result , _ = await self.visit(ast, env, path="")
        flow_nodes = await self._build_flow_nodes(env|result)
        #print("\n\n###############################FLOW NODES",flow_nodes)
        await self.runner.add_file(name,flow_nodes)
        self.runner.create_session(session,name,env|result)
        return result
 


# ── Public API ────────────────────────────────────────────────────────────────

def create_parser():
    return Lark(GRAMMAR, parser='lalr', propagate_positions=True)

def parse(source: str, parser: Lark) -> dict:
    return DSLTransformer().transform(parser.parse(source))

async def execute(name, ast, functions, parser=None):
    if parser is None: parser = create_parser()
    ast = parse(ast, parser) if isinstance(ast, str) else ast
    return await Interpreter().run(name, ast, env=functions)