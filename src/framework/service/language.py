"""
DSL Language — Parser · Interpreter · DAG Compiler
====================================================
Tre livelli distinti con responsabilità nette:

  DSLTransformer   Lark parse tree → AST dict
  Interpreter      AST dict → valori Python  (evaluator puro)
  DAGGenerator     AST dict → flow.node[]    (compilatore DAG)
"""

import asyncio
import inspect
import operator

from lark import Lark, Transformer, Token, v_args
from dataclasses import dataclass, field

import framework.service.scheme as scheme
import framework.service.flow   as flow
import framework.service.load   as load

# ============================================================================
# GRAMMAR
# ============================================================================

GRAMMAR = r"""
start: dictionary | [item (item)*] -> dictionary_node

dictionary: "{" [item (item)*] "}" -> dictionary_node

item: (pair|type_sequence) ASSIGN_OP sequence ";"? | (atom|sequence) COLON_OP sequence ";"?

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

?atom.7: value | identifier | tuple | list | dictionary | function_call | function_value

?tuple: "(" [sequence] ")" -> tuple_node | "(" [type_sequence] ")" -> tuple_node
pair.6: atom ":" atom
declaration.5: atom ":=" atom
?list: "[" [sequence] "]" -> list_node

function_call: identifier "(" [sequence|type_sequence] ")"
function_value.10: tuple dictionary tuple

identifier: CNAME            -> identifier
          | QUALIFIED_CNAME  -> identifier
          | "@" CNAME        -> context_var
          | "@" QUALIFIED_CNAME -> context_var

value: SIGNED_NUMBER -> number
     | STRING        -> string
     | "true"i       -> true
     | "false"i      -> false
     | "none"i       -> any_val

PIPE:           "|>"
ASSIGN_OP:      ":="
COLON_OP:       ":"
COMPARISON_OP:  "==" | "!=" | ">=" | "<=" | ">" | "<"
ARITHMETIC_OP:  "+" | "-" | "*" | "/" | "%"
STRING:         ESCAPED_STRING | SINGLE_QUOTED_STRING
SINGLE_QUOTED_STRING: /'[^']*'/
FILTER_PATTERN: "*[" CNAME "=" STRING "]"
QUALIFIED_CNAME: CNAME ("." (CNAME|INT|FILTER_PATTERN|"*"))+
INT: /[0-9]+/

%import common.SIGNED_NUMBER
%import common.ESCAPED_STRING
%import common.CNAME
%import common.WS
%ignore WS

COMMENT: /\/\/[^\n]*/ | /\/\*[\s\S]*?\*\//
%ignore COMMENT
"""

# ============================================================================
# CONSTANTS
# ============================================================================

OPS_MAP = {
    '+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV', '%': 'MOD', '^': 'POW',
    '==': 'EQ', '!=': 'NEQ', '>=': 'GTE', '<=': 'LTE', '>': 'GT', '<': 'LT',
}

OPS_FUNCTIONS = {
    'OP_ADD': operator.add,      'OP_SUB': operator.sub,
    'OP_MUL': operator.mul,      'OP_DIV': operator.truediv,
    'OP_MOD': operator.mod,      'OP_POW': operator.pow,
    'OP_EQ':  operator.eq,       'OP_NEQ': operator.ne,
    'OP_GT':  operator.gt,       'OP_LT':  operator.lt,
    'OP_GTE': operator.ge,       'OP_LTE': operator.le,
    'OP_AND': lambda a, b: a and b,
    'OP_OR':  lambda a, b: a or b,
    'OP_NOT': lambda a: not a,
}

TYPE_MAP = {
    'natural': int,  'integer': int,   'real': float,  'rational': float,
    'boolean': bool, 'complex': complex,'matrix': list, 'vector': list, 'set': set,
    'int': int,  'str': str,   'bool': bool,  'dict': dict,
    'list': list,'any': object,'type': dict,  'tuple': tuple, 'function': tuple,
    'i8': int, 'i16': int, 'i32': int, 'i64': int,
    'n8': int, 'n16': int, 'n32': int, 'n64': int,
    'f32': float, 'f64': float,
}

CUSTOM_TYPES = {}

DSL_FUNCTIONS = {
    'resource':  load.resource,
    'transform': scheme.transform,
    'get':       scheme.get,
    'normalize': scheme.normalize,
    'put':       scheme.put,
    'format':    scheme.format,
    'convert':   scheme.convert,
    'keys':      lambda d: list(d.keys()) if isinstance(d, dict) else [],
    'values':    lambda d: list(d.values()) if isinstance(d, dict) else [],
    'union':     lambda a, b: {**a, **b},
    'print':     lambda *inputs: (print(*inputs), inputs)[1],
    'pass':      lambda *inputs: inputs,
} | TYPE_MAP | {'extension': 'py'}

# ============================================================================
# SUPPORT TYPES
# ============================================================================

@dataclass(frozen=True)
class LazyBinOp:
    fn:          callable = field(repr=False, compare=False)
    description: str
    def __call__(self, *args, **kwargs): return self.fn(*args, **kwargs)
    def __repr__(self):                  return self.description

@dataclass(frozen=True)
class ContextVar:
    name: str
    def __call__(self, *data, **ctx): return scheme.get(ctx, self.name)
    def __repr__(self):               return self.name

class DSLRuntimeError(Exception):
    def __init__(self, message, meta=None, source_code=None):
        if meta:
            sl, sc = meta.get("line"), meta.get("column")
            el, ec = meta.get("end_line"), meta.get("end_column")
            if sl is not None:
                loc = f"line {sl}:{sc} - {el}:{ec}" if el else f"line {sl}, col {sc}"
                message += f" ({loc})"
                if source_code:
                    lines = source_code.splitlines() if isinstance(source_code, str) else source_code
                    if 1 <= sl <= len(lines):
                        message += f"\n  {lines[sl-1]}\n  {' '*(sc-1)}^"
        super().__init__(message)

# ============================================================================
# DSL TRANSFORMER  —  Lark parse tree → AST dict
# ============================================================================

@v_args(meta=True)
class DSLTransformer(Transformer):

    def _node(self, meta, **fields):
        """Costruisce un nodo AST con posizione."""
        pos = {"line": meta.line, "column": meta.column,
               "end_line": meta.end_line, "end_column": meta.end_column} \
              if hasattr(meta, "line") \
              else {"line": None, "column": None, "end_line": None, "end_column": None}
        return {"meta": pos, **fields}

    # primitivi
    def number(self, m, n):
        v = str(n[0]); return self._node(m, type="number", value=float(v) if "." in v else int(v))
    def string(self, m, s):  return self._node(m, type="string",  value=str(s[0])[1:-1])
    def true(self, m, _):    return self._node(m, type="bool",    value=True)
    def false(self, m, _):   return self._node(m, type="bool",    value=False)
    def any_val(self, m, _): return self._node(m, type="any")
    def function_value(self, m, a):
        return self._node(m, type="function_def", params=a[0], body=a[1], return_type=a[2])

    # nomi
    def identifier(self, m, s):   return self._node(m, type="var",         name=str(s[0]))
    def context_var(self, m, s):  return self._node(m, type="context_var", name=str(s[0]))
    def key(self, m, a):
        return {"type": "var", "name": str(a[0]),
                "meta": {"line": m.line, "column": m.column}} \
               if isinstance(a[0], Token) else a[0]

    # strutture
    def _unwrap(self, items, t):
        items = [i for i in items if i is not None]
        if len(items) == 1 and isinstance(items[0], dict) and items[0].get("type") == "sequence":
            items = items[0]["items"]
        return items
    def sequence(self, m, items):
        return self._node(m, type="sequence", items=[i for i in items if i is not None])
    def tuple_node(self, m, items):    return self._node(m, type="tuple",  items=self._unwrap(items, "tuple"))
    def list_node(self, m, items):     return self._node(m, type="list",   items=self._unwrap(items, "list"))
    def dictionary_node(self, m, items):
        return self._node(m, type="dict", items=[i for i in items if i is not None])

    # dichiarazioni
    def declaration(self, m, a): return self._node(m, type="declaration", target=a[0], value=a[1])
    def pair(self, m, a):        return self._node(m, type="pair",        key=a[0],    value=a[1])
    def item(self, m, tree):
        left, sep, right = tree[0], str(tree[1]), tree[2]
        return self._node(m, type="declaration" if sep == ":=" else "pair",
                          **{"target": left, "value": right} if sep == ":=" else {"key": left, "value": right})

    # funzioni
    def function_call(self, m, tree):
        inputs = tree[1].get("items", []) \
                 if isinstance(tree[1], dict) and tree[1]["type"] == "sequence" \
                 else [tree[1]]
        args, kwargs = [], {}
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("type") == "pair":
                kwargs[inp["key"]["name"]] = inp["value"]
            else:
                args.append(inp)
        return self._node(m, type="call", name=tree[0].get("name"), args=args, kwargs=kwargs)

    # espressioni
    def binary_op(self, m, a):
        return self._node(m, type="binop", op="*" if len(a)==2 else str(a[1]),
                          left=a[0], right=a[-1])
    def power(self, m, a):   return self._node(m, type="binop", op="^",   left=a[0], right=a[1])
    def not_op(self, m, a):  return self._node(m, type="not",             value=a[0])
    def and_op(self, m, a):  return self._node(m, type="binop", op="and", left=a[0], right=a[1])
    def or_op(self, m, a):   return self._node(m, type="binop", op="or",  left=a[0], right=a[1])
    def pipe_node(self, m, items):
        return self._node(m, type="pipe", steps=[i for i in items if not isinstance(i, Token)])
    def start(self, m, items): return items[0]

# ============================================================================
# INTERPRETER  —  AST dict → valori Python  (evaluator puro)
# ============================================================================
#
# Responsabilità: valutare un nodo AST in un env, restituire (valore, env).
# Non sa nulla di DAG, nodi o lifting.
# Il DAGGenerator lo chiama attraverso le closures eval_item / eval_expr / eval_call.
#
# Invarianti:
#   • non incontra mai "pipe" o "dict" — il DAGGenerator li ha già espansi
#   • non usa flow.act (solo invoke() lo fa, per chiamate esterne al DAG)
# ============================================================================

class Interpreter:

    def __init__(self):
        self._stack: list = []   # solo per arricchire i messaggi d'errore

    # ── dispatch ──────────────────────────────────────────────────────────────

    async def visit(self, node, env):
        if not isinstance(node, dict): return node, env
        t = node.get("type")
        if t == "pipe":
            raise DSLRuntimeError("BUG: pipe non espansa dal DAGGenerator", node.get("meta"))
        method = getattr(self, f"visit_{t}", None)
        if not method:
            raise DSLRuntimeError(f"Tipo AST sconosciuto: '{t}'", node.get("meta"))
        self._stack.append(node)
        try:
            return await method(node, env)
        except DSLRuntimeError as e:
            trace = " -> ".join(
                f"{n['type']}({n.get('meta',{}).get('line','?')}:{n.get('meta',{}).get('column','?')})"
                for n in self._stack)
            e.args = (f"{e.args[0]} | Stack: {trace}",); raise
        finally:
            self._stack.pop()

    # ── primitivi ─────────────────────────────────────────────────────────────

    async def visit_number(self, n, env):      return n["value"], env
    async def visit_string(self, n, env):      return n["value"], env
    async def visit_bool(self, n, env):        return n["value"], env
    async def visit_any(self, n, env):         return None, env
    async def visit_identifier(self, n, env):  return n["name"], env
    async def visit_var(self, n, env):         return scheme.get(env, n["name"], n["name"]), env
    async def visit_context_var(self, n, env): return ContextVar(n["name"]), env
    async def visit_function_def(self, n, env):
        params      = n["params"].get("items", [n["params"]])
        return_type = n["return_type"].get("items", [n["return_type"]])
        return (params, n["body"], return_type), env

    # ── dichiarazioni ─────────────────────────────────────────────────────────

    async def visit_declaration(self, node, env):
        val, _ = await self.visit(node["value"],  env)
        key, _ = await self.visit(node["target"], env)
        meta   = node.get("meta")
        items  = key if isinstance(key[0], tuple) else [key]
        if node["target"]["type"] == "pair":
            tipo, name = node["target"]["key"]["name"], node["target"]["value"]["name"]
            if tipo == "type":
                CUSTOM_TYPES[name] = val; return (name, val), env
            return (name, await self._check_type(val, tipo, meta, name)), env
        keys, values = [], []
        for i, _ in enumerate(items):
            tipo = node["target"]["items"][i]["key"]["name"]
            name = node["target"]["items"][i]["value"]["name"]
            if tipo == "type": CUSTOM_TYPES[name] = val
            keys.append(name)
            values.append(await self._check_type(
                val[i] if isinstance(val, tuple) else val, tipo, meta, name))
        return (tuple(keys), tuple(values)), env

    async def visit_pair(self, node, env):
        value, _ = await self.visit(node["value"], env)
        key = node["key"]["name"] if node["key"]["type"] == "var" \
              else (await self.visit(node["key"], env))[0]
        return (key, value), env

    async def visit_dict(self, node, env):
        result = {}
        for item in node["items"]:
            res, _ = await self.visit(item, env | result)
            key, value = res
            if isinstance(key, tuple) and not isinstance(value, tuple) and len(key) == 2:
                key = key[1]
            if isinstance(key, tuple) and isinstance(value, tuple):
                result.update(zip(key, value))
            else:
                result[key] = value
        return result, env

    # ── collezioni ────────────────────────────────────────────────────────────

    async def visit_tuple(self, node, env):
        items = []
        for item in node["items"]: val, env = await self.visit(item, env); items.append(val)
        return tuple(items), env

    async def visit_sequence(self, node, env):
        items = []
        for item in node["items"]: val, env = await self.visit(item, env); items.append(val)
        return tuple(items), env

    async def visit_list(self, node, env):
        items = []
        for item in node["items"]: val, env = await self.visit(item, env); items.append(val)
        return items, env

    # ── logica e matematica ───────────────────────────────────────────────────

    async def visit_binop(self, node, env):
        left,  env = await self.visit(node["left"],  env)
        right, env = await self.visit(node["right"], env)
        op = node["op"]
        if isinstance(left,  tuple): left  = left[0]
        if isinstance(right, tuple): right = right[0]
        if callable(left) or callable(right):
            def lazy(*_, **ctx):
                l = left(**ctx)  if callable(left)  else left
                r = right(**ctx) if callable(right) else right
                return OPS_FUNCTIONS[f"OP_{OPS_MAP.get(op, op.upper())}"](l, r)
            return LazyBinOp(lazy, f"{left!r} {op} {right!r}"), env
        OPS = {
            "and": lambda: left and right,  "or":  lambda: left or right,
            "==":  lambda: left == right,   "!=":  lambda: left != right,
            ">":   lambda: left > right,    "<":   lambda: left < right,
            ">=":  lambda: left >= right,   "<=":  lambda: left <= right,
            "+":   lambda: left + right,    "-":   lambda: left - right,
            "*":   lambda: left * right,    "/":   lambda: left / right,
            "%":   lambda: left % right,    "^":   lambda: left ** right,
        }
        try:
            fn = OPS.get(op)
            return (fn() if fn else OPS_FUNCTIONS[f"OP_{OPS_MAP.get(op)}"](left, right)), env
        except Exception as e:
            raise DSLRuntimeError(f"Errore '{op}': {e}", node.get("meta"))

    async def visit_not(self, node, env):
        val, env = await self.visit(node["value"], env)
        return not val, env

    # ── chiamate ─────────────────────────────────────────────────────────────

    async def _call_dsl_fn(self, fn_triple, args, kwargs):
        """Esegue una funzione definita nel DSL (tripla params/body/return)."""
        params_ast, body_ast, return_ast = fn_triple
        local_env = {}
        for p, a in zip(params_ast, args):
            local_env[p["value"]["name"]] = await self._check_type(
                a, p["key"]["name"], p.get("meta"), p["value"]["name"])
        result, _ = await self.visit(body_ast, local_env)
        out = []
        for ty in return_ast:
            (tipo, name), _ = await self.visit(ty, local_env)
            if name in result:
                out.append(await self._check_type(result[name], tipo, ty.get("meta"), name))
        return out[0] if len(out) == 1 else out

    async def visit_call(self, node, env, args=(), kwargs=None):
        name, meta = node.get("name"), node.get("meta")
        ast_args   = [(await self.visit(a, env))[0] for a in node.get("args", [])]
        ast_kwargs = {k: (await self.visit(v, env))[0] for k, v in node.get("kwargs", {}).items()}
        all_args   = list(args) + ast_args
        all_kwargs = {**(kwargs or {}), **ast_kwargs}
        fn = scheme.get(env, str(name))
        if callable(fn):
            result = await fn(*all_args, **all_kwargs) \
                     if asyncio.iscoroutinefunction(fn) else fn(*all_args, **all_kwargs)
        elif isinstance(fn, tuple) and len(fn) == 3:
            result = await self._call_dsl_fn(fn, all_args, all_kwargs)
        else:
            raise DSLRuntimeError(f"Funzione sconosciuta: '{name}'", meta)
        return result, env

    async def invoke(self, function, args=(), kwargs=None):
        """Esegue una funzione dall'esterno del DAG — unico uso lecito di flow.act."""
        if callable(function):
            s = flow.step(function, *args, **(kwargs or {}))
        elif isinstance(function, tuple) and len(function) == 3:
            s = flow.step(self._call_dsl_fn, function, args, kwargs or {})
        else:
            raise DSLRuntimeError("Funzione sconosciuta")
        return await flow.act(s)

    # ── type checking ─────────────────────────────────────────────────────────

    async def _check_type(self, value, expected, meta, name):
        if expected in CUSTOM_TYPES:
            return await scheme.normalize(value, CUSTOM_TYPES[expected])
        py = TYPE_MAP.get(expected)
        if py and not (isinstance(value, py) and not (py is int and isinstance(value, bool))):
            raise DSLRuntimeError(
                f"Tipo errato per '{name}': atteso {expected}, ottenuto {type(value).__name__}", meta)
        return value

    async def resolve(self, val, env):
        while callable(val):
            res = val(**env)
            val = await res if inspect.isawaitable(res) else res
        return val

# ============================================================================
# DAG GENERATOR  —  AST dict → flow.node[]  (compilatore DAG)
# ============================================================================
#
# Regole di compilazione:
#
#   dict top-level   →  _nodes_from_dict:  nodi con naming <var>.<key>
#   pipe top-level   →  _pipe_to_nodes:    catena <var>, _pipe_<var>_i
#   pipe annidata    →  _lift:             nodo sintetico _anf_<ctx>_N
#   dict annidato    →  visit_dict:        valutato inline dal visitor (letterale)
#   expr singola     →  _nodes_from_single
#   multi-var        →  _nodes_from_multi
#
# Il visitor gestisce direttamente i dict inline (dentro tuple/list/args)
# perché sono letterali strutturali senza dipendenze DAG proprie.
# Solo le pipe annidate dentro espressioni diventano nodi DAG sintetici.
# ============================================================================

class DAGGenerator:
    """Compila un AST DSL in un grafo DAG ed esegue tutto via flow.run()."""

    def __init__(self, env=None):
        self.env    = env if env is not None else {}
        self._interp = Interpreter()

    # ── API pubblica ──────────────────────────────────────────────────────────

    @staticmethod
    def keys(node) -> list:
        """Nomi delle variabili definite da un item AST."""
        if not isinstance(node, dict): return []
        t = node.get("type")
        if t == "declaration": return DAGGenerator.keys(node.get("target"))
        if t == "pair":
            k, v = node.get("key", {}), node.get("value", {})
            if v.get("type") in ("var","identifier") and k.get("type") in ("var","identifier"):
                return [v["name"]]
            kn = k.get("value") if k.get("type") == "string" else k.get("name")
            return [kn] if kn else []
        if t in ("var","identifier"): return [node["name"]]
        if t in ("sequence","tuple","list","dictionary_node","dict"):
            return [k for x in node.get("items",[]) for k in DAGGenerator.keys(x)]
        return []

    @staticmethod
    def deps(node) -> set:
        """Variabili referenziate da un sotto-AST."""
        if isinstance(node, (list, tuple)):
            return set().union(*(DAGGenerator.deps(x) for x in node))
        if isinstance(node, str): return {node.split(".")[0]}
        if isinstance(node, dict):
            t = node.get("type")
            if t in ("var","identifier"): return {node["name"].split(".")[0]}
            if t == "context_var":        return set()
            return set().union(*(DAGGenerator.deps(v) for k,v in node.items()
                                 if k not in ("meta","type")))
        return set()

    @staticmethod
    def ext_deps(node, defined, exclude=frozenset()) -> list:
        """Dipendenze esterne: presenti nel nodo e nel DAG globale."""
        return [d for d in DAGGenerator.deps(node) if d in defined and d not in exclude]

    @staticmethod
    def clean(ctx) -> dict:
        """Converte il contesto di flow.run() in valori puri."""
        return {k: flow.value_of(v) for k, v in ctx.items()} if isinstance(ctx, dict) else ctx

    # ── lifting ANF ───────────────────────────────────────────────────────────
    #
    # _lift() solleva SOLO le pipe in nodi DAG sintetici.
    # I dict non vengono mai toccati da _lift: quelli top-level sono gestiti
    # da _nodes_from_dict (naming semantico), quelli annidati inside
    # espressioni (tuple, list, args) vengono valutati inline dal visitor
    # perché non hanno dipendenze DAG proprie — sono letterali strutturali.

    @staticmethod
    def _fresh(ctx, counter):
        n = counter[0]; counter[0] += 1; return f"_anf_{ctx}_{n}"

    def _lift(self, node, ctx, defined, ev_expr, ev_call, lifted, counter):
        """Solleva le pipe annidate in nodi DAG. I dict vengono lasciati invariati."""
        if not isinstance(node, dict): return node
        t = node.get("type")

        if t == "pipe":
            name  = self._fresh(ctx, counter)
            steps = [self._lift(s, name, defined | {name}, ev_expr, ev_call, lifted, counter)
                     for s in node["steps"]]
            lifted.extend(self._pipe_to_nodes(
                {"type": "pipe", "steps": steps, "meta": node.get("meta")},
                sink=name, defined=defined | {name}, ev_expr=ev_expr, ev_call=ev_call))
            return {"type": "var", "name": name, "meta": node.get("meta")}

        # Per tutti gli altri nodi (incluso dict): ricorsione solo sui figli,
        # senza estrarre il nodo stesso — i dict rimangono nell'AST.
        return {k: (self._lift_children(v, ctx, defined, ev_expr, ev_call, lifted, counter)
                    if k not in ("meta","type") else v)
                for k, v in node.items()}

    def _lift_children(self, value, ctx, defined, ev_expr, ev_call, lifted, counter):
        if isinstance(value, list):
            return [self._lift(x, ctx, defined, ev_expr, ev_call, lifted, counter) for x in value]
        if isinstance(value, dict):
            return self._lift(value, ctx, defined, ev_expr, ev_call, lifted, counter)
        return value

    # ── pipe → catena di nodi ─────────────────────────────────────────────────

    def _pipe_to_nodes(self, pipe_ast, sink, defined, ev_expr, ev_call):
        """sink := expr |> f1 |> f2  →  catena di nodi DAG."""
        steps, nodes, prev = pipe_ast.get("steps", []), [], None
        for i, step in enumerate(steps):
            name     = sink if i == len(steps)-1 else f"_pipe_{sink}_{i}"
            ext      = self.ext_deps(step, defined, exclude={sink})
            all_deps = ([prev] + ext) if prev else ext
            if i == 0:
                def _src(a=step):
                    async def src(**kw): return (await ev_expr(a, kw))[0]
                    return src
                fn = _src()
            else:
                def _stp(a=step, up=prev):
                    async def s(**kw): return (await ev_call(a, kw, args=[kw.get(up)]))[0]
                    return s
                fn = _stp()
            nodes.append(flow.node(name, fn, deps=all_deps)); prev = name
        return nodes

    # ── strategie item ────────────────────────────────────────────────────────

    def _item_worker(self, item, ev_item):
        async def w(**kw):
            (key, val), _ = await ev_item(item, kw)
            return dict(zip(key, val)) if isinstance(key, tuple) and isinstance(val, tuple) else val
        return w

    def _nodes_from_single(self, name, item, deps, ev_item):
        return [flow.node(name, self._item_worker(item, ev_item), deps=deps)]

    def _nodes_from_multi(self, keys, item, deps, ev_item):
        grp = "_grp_" + "_".join(keys)
        def _ex(k, g=grp):
            async def ex(**kw): return (kw.get(g) or {}).get(k)
            return flow.node(k, ex, deps=[g])
        return [flow.node(grp, self._item_worker(item, ev_item), deps=deps),
                *[_ex(k) for k in keys]]

    def _nodes_from_dict(self, var_name, dict_node, defined, ev_expr, ev_call, ev_item):
        """
        Dict top-level → nodi DAG con naming semantico <var>.<key>.

            imports: { 'load': resource(...) }
            ──────────────────────────────────────────
            imports.load    eval resource(...)    deps: ext
            imports         {"load": ↑}           deps: [imports.load]

        I dict annidati come valori vengono espansi ricorsivamente.
        Le pipe dentro i valori vengono lift-ate normalmente.
        """
        pair_names = {}
        nodes      = []
        # aggiorna defined con i nodi che stiamo per creare, così le dep
        # tra fratelli dello stesso dict sono risolte correttamente
        all_children = {
            f"{var_name}.{(item.get('key') or item.get('target',{}).get('key',{})).get('value') or (item.get('key') or item.get('target',{}).get('key',{})).get('name','')}"
            for item in dict_node.get("items", [])
        } - {""}
        defined_here = defined | all_children | {var_name}

        for item in dict_node.get("items", []):
            raw_key = item.get("key", {}) if item.get("type") == "pair"                       else item.get("target", {}).get("key", {})
            key_str = raw_key.get("value") if raw_key.get("type") == "string"                       else raw_key.get("name", "")
            if not key_str: continue

            child_name = f"{var_name}.{key_str}"
            val_ast    = item.get("value", {})

            if isinstance(val_ast, dict) and val_ast.get("type") == "dict":
                # Valore è un dict: espansione ricorsiva
                nodes.extend(self._nodes_from_dict(
                    child_name, val_ast, defined_here, ev_expr, ev_call, ev_item))
            else:
                # Valore è un'espressione: solleva solo pipe al suo interno
                lifted, counter = [], [0]
                val_lifted = self._lift(val_ast, child_name, defined_here,
                                        ev_expr, ev_call, lifted, counter)
                nodes.extend(lifted)
                child_deps = self.ext_deps(
                    val_lifted, defined_here | {n["name"] for n in lifted})
                def _vw(a=val_lifted):
                    async def w(**kw): return (await ev_expr(a, kw))[0]
                    return w
                nodes.append(flow.node(child_name, _vw(), deps=child_deps))

            pair_names[key_str] = child_name

        # Assemblatore: legge i valori dai nodi figli tramite kw (dep → kw key)
        def _asm(_k=dict(pair_names)):
            async def a(**kw): return {k: kw.get(v) for k, v in _k.items()}
            return a
        nodes.append(flow.node(var_name, _asm(), deps=list(pair_names.values())))
        return nodes

    # ── compilazione ──────────────────────────────────────────────────────────

    def compile(self, ast, env) -> list:
        """AST → lista piatta di flow.node() pronta per flow.run()."""
        items   = ast.get("items", [])
        defined = {k for item in items for k in self.keys(item)}

        async def ev_item(item, kw): return await self._interp.visit(item, env | kw)
        async def ev_expr(ast,  kw): return await self._interp.visit(ast,  env | kw)
        async def ev_call(ast, kw, args=()):
            return await self._interp.visit_call(ast, env | kw, args=args)

        nodes = []
        for item in items:
            item_keys = self.keys(item)
            if not item_keys: continue

            lifted, counter = [], [0]
            item_lifted = self._lift(item, "_".join(item_keys), defined,
                                     ev_expr, ev_call, lifted, counter)
            nodes.extend(lifted)

            defined_ext = defined | {n["name"] for n in lifted}
            value_node  = item_lifted.get("value", item_lifted)
            item_deps   = self.ext_deps(value_node, defined_ext, exclude=set(item_keys))

            if value_node.get("type") == "dict" and len(item_keys) == 1:
                # Dict top-level: nodi con naming semantico <var>.<key>
                nodes += self._nodes_from_dict(item_keys[0], value_node, defined_ext,
                                               ev_expr, ev_call, ev_item)
            elif value_node.get("type") == "pipe" and len(item_keys) == 1:
                nodes += self._pipe_to_nodes(value_node, item_keys[0], defined_ext,
                                             ev_expr, ev_call)
            elif len(item_keys) == 1:
                nodes += self._nodes_from_single(item_keys[0], item_lifted, item_deps, ev_item)
            else:
                nodes += self._nodes_from_multi(item_keys, item_lifted, item_deps, ev_item)

        return nodes

    # ── esecuzione ────────────────────────────────────────────────────────────

    async def run(self, ast):
        """Unico entry point: compila e delega a flow.run()."""
        nodes = self.compile(ast, self.env)
        if not nodes:
            async def _root(**_):
                result, _ = await self._interp.visit(ast, self.env)
                return result
            nodes = [flow.node("__result__", _root)]
        return await flow.run(nodes)

# ============================================================================
# PUBLIC API
# ============================================================================

def create_parser():
    return Lark(GRAMMAR, parser='lalr', propagate_positions=True)

def parse(source: str, parser: Lark) -> dict:
    return DSLTransformer().transform(parser.parse(source))

async def execute(source_or_ast, parser, functions):
    ast = parse(source_or_ast, parser) if isinstance(source_or_ast, str) else source_or_ast
    return await DAGGenerator(functions).run(ast)