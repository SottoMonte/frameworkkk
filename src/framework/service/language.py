"""
DSL Language Interpreter
========================
Complete & faithful version
- NO global parser
- TriggerEngine separated
- Fully compatible with original DSL
"""

import asyncio
import inspect
import operator

from lark import Lark, Transformer, Token, v_args

import framework.service.scheme as scheme
import framework.service.flow as flow
import framework.service.load as load

from dataclasses import dataclass, field

# ============================================================================
# GRAMMAR
# ============================================================================

GRAMMAR = r"""
// ==========================================
// PUNTO DI INGRESSO (ROOT)
// ==========================================
start: dictionary | [item (item)*] -> dictionary_node

// ==========================================
// STRUTTURE DATI (DIZIONARI E ITEM)
// ==========================================
dictionary: "{" [item (item)*] "}" -> dictionary_node

#item: (atom|sequence|type_sequence) (ASSIGN_OP sequence ";"? | COLON_OP sequence ";"?)

item: (pair|type_sequence) ASSIGN_OP sequence ";"? | (atom|sequence) COLON_OP sequence ";"?

#item: (atom|sequence|type_sequence) ";"
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
declaration.5: atom ":=" atom
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
     | "none"i              -> any_val

PIPE: "|>"
ASSIGN_OP: ":="
COLON_OP: ":"
COMPARISON_OP: "==" | "!=" | ">=" | "<=" | ">" | "<"
ARITHMETIC_OP: "+" | "-" | "*" | "/" | "%"
STRING: ESCAPED_STRING | SINGLE_QUOTED_STRING
SINGLE_QUOTED_STRING: /'[^']*'/
#QUALIFIED_CNAME: CNAME ("." (CNAME|INT|"*"))+
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


# ============================================================================
# ERRORS
# ============================================================================

# ============================================================================
# OPS / TYPES
# ============================================================================

OPS_MAP = {
    '+':'ADD','-':'SUB','*':'MUL','/':'DIV','%':'MOD','^':'POW',
    '==':'EQ','!=':'NEQ','>=':'GTE','<=':'LTE','>':'GT','<':'LT'
}

OPS_FUNCTIONS = {
    'OP_ADD': operator.add, 'OP_SUB': operator.sub,
    'OP_MUL': operator.mul, 'OP_DIV': operator.truediv,
    'OP_MOD': operator.mod, 'OP_POW': operator.pow,
    'OP_EQ': operator.eq, 'OP_NEQ': operator.ne,
    'OP_GT': operator.gt, 'OP_LT': operator.lt,
    'OP_GTE': operator.ge, 'OP_LTE': operator.le,
    'OP_AND': lambda a, b: a and b,
    'OP_OR': lambda a, b: a or b,
    'OP_NOT': lambda a: not a,
}

TYPE_MAP = {
    'natural': int,
    'integer': int,
    'real': float,
    'rational': float,
    'boolean': bool,
    'complex': complex,
    'matrix': list,
    'vector': list,
    'set': set,
    #Macchine
    'int': int,
    'i8': int, 
    'i16': int, 
    'i32': int, 
    'i64': int, 
    'n8': int, 
    'n16': int, 
    'n32': int, 
    'n64': int, 
    'f32': float, 
    'f64': float, 
    'str': str, 
    'bool': bool,
    'dict': dict, 
    'list': list, 
    'any': object, 
    'type': dict,
    'tuple': tuple,
    'function': tuple,
}

CUSTOM_TYPES = {}

DSL_FUNCTIONS = {
    'resource': load.resource,
    #'transaction': flow.transaction,
    'transform': scheme.transform,
    'get': scheme.get,
    'normalize': scheme.normalize,
    'put': scheme.put,
    'format': scheme.format,
    #'foreach': flow.foreach,
    #'retry': flow.retry,
    'convert': scheme.convert,
    'keys': lambda d: list(d.keys()) if isinstance(d, dict) else [],
    'values': lambda d: list(d.values()) if isinstance(d, dict) else [],
    'union': lambda a,b: {**a,**b},
    'print': lambda *inputs: (print(*inputs), inputs)[1],
    'pass': lambda *inputs: inputs,
    #'assert': flow.assertt,
    #'guard': flow.guard,
    #'when': flow.when,
}|TYPE_MAP|{'extension':'py'}


# ============================================================================
# AST HELPERS
# ============================================================================

is_var = lambda n: isinstance(n, tuple) and n[:1] == ('VAR',)
is_typed = lambda n: isinstance(n, tuple) and n[:1] == ('TYPED',)
is_call = lambda n: isinstance(n, tuple) and n[:1] == ('CALL',)
is_expression = lambda n: isinstance(n, tuple) and n[:1] == ('EXPRESSION',)
is_function_def = lambda n: isinstance(n, tuple) and len(n) == 3 and isinstance(n[1], dict)
is_trigger = lambda n: is_call(n) or (isinstance(n, tuple) and '*' in n)

get_name = lambda n: n[1] if is_var(n) else n[2] if is_typed(n) else str(n)
get_type = lambda n: n[1] if is_typed(n) else None

# ============================================================================
# TRANSFORMER (IDENTICO ALL'ORIGINALE)
# ============================================================================

from lark import Transformer, v_args


@v_args(meta=True)
class DSLTransformer(Transformer):

    # -------------------------------------------------
    # helper
    # -------------------------------------------------

    def with_meta(self, node, meta, fallback=None):
        if hasattr(meta, "line"):
            node["meta"] = {
                "line": meta.line,
                "column": meta.column,
                "end_line": meta.end_line,
                "end_column": meta.end_column
            }
        elif fallback and "meta" in fallback:
            node["meta"] = fallback["meta"]
        else:
            node["meta"] = {
                "line": None,
                "column": None,
                "end_line": None,
                "end_column": None

            }
        return node

    # -------------------------------------------------
    # PRIMITIVI
    # -------------------------------------------------

    def number(self, meta, n):
        v = str(n[0])
        return self.with_meta({
            "type": "number",
            "value": float(v) if "." in v else int(v)
        }, meta)

    def string(self, meta, s):
        return self.with_meta({
            "type": "string",
            "value": str(s[0])[1:-1]
        }, meta)

    def true(self, meta, _):
        return self.with_meta({
            "type": "bool",
            "value": True
        }, meta)

    def false(self, meta, _):
        return self.with_meta({
            "type": "bool",
            "value": False
        }, meta)

    def any_val(self, meta, _):
        return self.with_meta({
            "type": "any"
        }, meta)

    def function_value(self, meta, a):
        return self.with_meta({
            "type": "function_def",
            "params": a[0],
            "body": a[1],
            "return_type": a[2]
        }, meta)

    # -------------------------------------------------
    # VARIABILI / NOMI
    # -------------------------------------------------

    def identifier(self, meta, s):
        # Fondamentale: usiamo "identifier" come tipo per il nome puro
        return self.with_meta({
            "type": "var", 
            "name": str(s[0])
        }, meta)

    def context_var(self, meta, s):
        return self.with_meta({
            "type": "context_var",
            "name": str(s[0])
        }, meta)

    def key(self, meta, a):
        # Se arriva un Tree, estrai il token e trasformalo
        if isinstance(a[0], Token):
            return {"type": "var", "name": str(a[0]), "meta": {"line": meta.line, "column": meta.column}}
        return a[0]

    # -------------------------------------------------
    # STRUTTURE
    # -------------------------------------------------
    
    def sequence(self, meta, items):
        items = [i for i in items if i is not None]
        
        return self.with_meta({
            "type": "sequence",
            "items": items
        }, meta)

    def tuple_node(self, meta, items):
        items = [i for i in items if i is not None]
        
        if len(items) == 1 and isinstance(items[0], dict) and items[0].get("type") == "sequence":
            real_items = items[0]["items"]
        else:
            real_items = items
        return self.with_meta({
            "type": "tuple",
            #"items": items
            "items":real_items
        }, meta)

    def list_node(self, meta, items):
        items = [i for i in items if i is not None]
        if len(items) == 1 and isinstance(items[0], dict) and items[0].get("type") == "sequence":
            real_items = items[0]["items"]
        else:
            real_items = items
        return self.with_meta({
            "type": "list",
            #"items": [i for i in items if i is not None]
            "items":real_items
        }, meta)

    def dictionary_node(self, meta, items):
        return self.with_meta({
            "type": "dict",
            "items": [i for i in items if i is not None]
        }, meta)

    # -------------------------------------------------
    # DICHIARAZIONI / MAPPING
    # -------------------------------------------------
    
    def declaration(self, meta, a):
        #print("##############################declaration", a[0])
        return self.with_meta({
            "type": "declaration",
            "target": a[0],
            "value": a[1]
        }, meta)

    def pair(self, meta, a):
        #print("##############################pair", a)
        return self.with_meta({
            "type": "pair",
            "key": a[0],
            "value": a[1]
        }, meta)

    def item(self, meta, tree):
        # tree[0] è il lato sinistro (atom, sequence, ecc.)
        # tree[1] è il token (il separatore ':=' o ':')
        # tree[2] è il lato destro (la sequence dopo il separatore)
        #print("\n#######",tree)
        #return tree[0]
        left_side = tree[0]
        separator = str(tree[1]) # ":=" o ":"
        right_side = tree[2]
        
        if separator == ":=":
            #print("\n#######",left_side)
            return self.with_meta({
                "type": "declaration",
                "target": left_side,
                "value": right_side
            }, meta)
        else:
            return self.with_meta({
                "type": "pair",
                "key": left_side,
                "value": right_side
            }, meta)

    # -------------------------------------------------
    # FUNZIONI
    # -------------------------------------------------

    def function_call3(self, meta, a):
        fn = a[0]
        args = []
        kwargs = {}

        '''if len(a) > 1 and a[1] is not None:
            seq = a[1]
            items = seq.get("items", []) if isinstance(seq, dict) and seq.get("type") == "sequence" else [seq]
            for item in items:
                print("item",item)
                if isinstance(item, dict) and item.get("type") == "pair":
                    key_node = item["key"]
                    key_name = key_node["name"] if isinstance(key_node, dict) and key_node.get("type") == "var" else str(key_node)
                    kwargs[key_name] = item["value"]
                else:
                    args.append(item)'''
        if len(a) > 1 and a[1] is not None:
            seq = a[1]
            # Assicuriamoci che seq sia una lista piatta di elementi
            items = seq.get("items", []) if isinstance(seq, dict) and seq.get("type") in ["sequence", "tuple"] else [seq]
            
            for item in items:
                if isinstance(item, dict) and item.get("type") == "pair":
                    # È un keyword argument (chiave:valore)
                    key_name = item["key"]["name"] if isinstance(item["key"], dict) else str(item["key"])
                    kwargs[key_name] = item["value"]
                else:
                    # È un positional argument
                    args.append(item)
        #print("args",args,"kwargs",kwargs)
        return self.with_meta({
            "type": "call",
            "name": fn.get("name"),
            "args": args,
            "kwargs": kwargs
        }, meta)

    def function_call(self, meta, tree):
        # tree[0] è l'identificatore, tree[1] è la sequenza (se presente)
        fn = tree[0]
        #sss = tree[1]
        inputs = tree[1].get('items',[]) if isinstance(tree[1],dict) and tree[1]['type'] == "sequence" else [tree[1]]
        args = []
        kwargs = {}
        for input in inputs:
            if isinstance(input, dict) and input.get("type") in ["pair"]:
                key_node = input["key"]
                #key_name = key_node["name"] if isinstance(key_node, dict) and key_node.get("type") in ["var","context_var"] else str(key_node)
                key_name = key_node["name"]
                kwargs[key_name] = input["value"]
            else:
                args.append(input)
        return self.with_meta({
            "type": "call",
            "name": fn.get("name"),
            "args": args,
            "kwargs": kwargs
        }, meta)

    # -------------------------------------------------
    # ESPRESSIONI
    # -------------------------------------------------

    def binary_op(self, meta, a):
        if len(a) == 2:
            return self.with_meta({
                "type": "binop",
                "op": "*",
                "left": a[0],
                "right": a[1]
            }, meta)
        return self.with_meta({
            "type": "binop",
            "op": str(a[1]),
            "left": a[0],
            "right": a[2]
        }, meta)

    def power(self, meta, a):
        return self.with_meta({
            "type": "binop",
            "op": "^",
            "left": a[0],
            "right": a[1]
        }, meta)

    def not_op(self, meta, a):
        return self.with_meta({
            "type": "not",
            "value": a[0]
        }, meta)

    def and_op(self, meta, a):
        return self.with_meta({
            "type": "binop",
            "op": "and",
            "left": a[0],
            "right": a[1]
        }, meta)

    def or_op(self, meta, a):
        return self.with_meta({
            "type": "binop",
            "op": "or",
            "left": a[0],
            "right": a[1]
        }, meta)

    def pipe_node(self, meta, items):
        return self.with_meta({
            "type": "pipe",
            "steps": [i for i in items if not isinstance(i, Token)],
        }, meta)

    def start(self, meta, items):
        return items[0]

@dataclass(frozen=True)
class LazyBinOp:
    '''def __init__(self, fn, description):
        self.fn = fn
        self.description = description'''
    fn: callable = field(repr=False, compare=False)
    description: str
        
    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)
        
    def __repr__(self):
        return self.description

    '''def __eq__(self, other):
        if not isinstance(other, LazyBinOp):
            return False
        return self.description == other.description

    # 2. Definisci l'hash in base agli stessi campi usati in __eq__
    def __hash__(self):
        return hash(self.description)'''
@dataclass(frozen=True)
class ContextVar:
    name:str
    '''def __init__(self, name):
        self.name = name'''
    def __call__(self, *data, **data_context):
        return scheme.get(data_context, self.name)
    def __repr__(self):
        return self.name

class DSLRuntimeError(Exception):
    def __init__(self, message, meta=None, source_code=None):
        """
        source_code: stringa completa del DSL file (o lista di righe)
        """
        error_msg = message

        if meta:
            start_line = meta.get("line")
            start_col  = meta.get("column")
            end_line   = meta.get("end_line")
            end_col    = meta.get("end_column")

            if start_line is not None and start_col is not None:
                if end_line is not None and end_col is not None:
                    loc = f"line {start_line}:{start_col} - {end_line}:{end_col}"
                else:
                    loc = f"line {start_line}, col {start_col}"
                
                error_msg += f" ({loc})"

                # aggiungi la riga del file DSL, se fornita
                if source_code:
                    # source_code può essere stringa o lista di righe
                    lines = source_code.splitlines() if isinstance(source_code, str) else source_code
                    if 1 <= start_line <= len(lines):
                        code_line = lines[start_line - 1]
                        pointer = " " * (start_col - 1) + "^"
                        error_msg += f"\n  {code_line}\n  {pointer}"

        super().__init__(error_msg)

# ============================================================================
# ============================================================================
# INTERPRETER  —  AST dict → valori Python  (evaluator puro)
# ============================================================================

class Interpreter:

    def __init__(self): self._stack = []

    async def visit(self, node, env):
        if not isinstance(node, dict): return node, env
        t = node.get("type")
        if t == "pipe":
            raise DSLRuntimeError("BUG: pipe non espansa dal DAGGenerator", node.get("meta"))
        method = getattr(self, f"visit_{t}", None)
        if not method: raise DSLRuntimeError(f"Tipo AST sconosciuto: '{t}'", node.get("meta"))
        self._stack.append(node)
        try:
            return await method(node, env)
        except DSLRuntimeError as e:
            trace = " -> ".join(
                f"{n['type']}({n.get('meta',{}).get('line','?')}:{n.get('meta',{}).get('column','?')})"
                for n in self._stack)
            e.args = (f"{e.args[0]} | Stack: {trace}",); raise
        finally: self._stack.pop()

    async def visit_number(self, n, e):      return n["value"], e
    async def visit_string(self, n, e):      return n["value"], e
    async def visit_bool(self, n, e):        return n["value"], e
    async def visit_any(self, n, e):         return None, e
    async def visit_identifier(self, n, e):  return n["name"], e
    async def visit_var(self, n, e):         return scheme.get(e, n["name"], n["name"]), e
    async def visit_context_var(self, n, e): return ContextVar(n["name"]), e
    async def visit_function_def(self, n, e):
        p = n["params"].get("items", [n["params"]])
        r = n["return_type"].get("items", [n["return_type"]])
        return (p, n["body"], r), e

    async def visit_declaration(self, node, env):
        val, _ = await self.visit(node["value"],  env)
        key, _ = await self.visit(node["target"], env)
        meta   = node.get("meta")
        items  = key if isinstance(key[0], tuple) else [key]
        if node["target"]["type"] == "pair":
            tipo, name = node["target"]["key"]["name"], node["target"]["value"]["name"]
            if tipo == "type": CUSTOM_TYPES[name] = val; return (name, val), env
            return (name, await self._check(val, tipo, meta, name)), env
        keys, values = [], []
        for i, _ in enumerate(items):
            tipo = node["target"]["items"][i]["key"]["name"]
            name = node["target"]["items"][i]["value"]["name"]
            if tipo == "type": CUSTOM_TYPES[name] = val
            keys.append(name)
            values.append(await self._check(val[i] if isinstance(val,tuple) else val, tipo, meta, name))
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
            result.update(zip(key, value)) if isinstance(key, tuple) and isinstance(value, tuple) \
                else result.update({key: value})
        return result, env

    async def _collect(self, node, env, cast):
        items = []
        for item in node["items"]: val, env = await self.visit(item, env); items.append(val)
        return cast(items), env

    async def visit_tuple(self, n, e):    return await self._collect(n, e, tuple)
    async def visit_sequence(self, n, e): return await self._collect(n, e, tuple)
    async def visit_list(self, n, e):     return await self._collect(n, e, list)

    async def visit_binop(self, node, env):
        left, env  = await self.visit(node["left"],  env)
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
        OPS = {"and":lambda:left and right,"or":lambda:left or right,
               "==":lambda:left==right,"!=":lambda:left!=right,
               ">":lambda:left>right,"<":lambda:left<right,
               ">=":lambda:left>=right,"<=":lambda:left<=right,
               "+":lambda:left+right,"-":lambda:left-right,
               "*":lambda:left*right,"/":lambda:left/right,
               "%":lambda:left%right,"^":lambda:left**right}
        try:
            fn = OPS.get(op)
            return (fn() if fn else OPS_FUNCTIONS[f"OP_{OPS_MAP.get(op)}"](left, right)), env
        except Exception as e:
            raise DSLRuntimeError(f"Errore '{op}': {e}", node.get("meta"))

    async def visit_not(self, node, env):
        val, env = await self.visit(node["value"], env); return not val, env

    async def _call_dsl_fn(self, fn_triple, args, kwargs):
        params_ast, body_ast, return_ast = fn_triple
        local_env = {}
        for p, a in zip(params_ast, args):
            local_env[p["value"]["name"]] = await self._check(
                a, p["key"]["name"], p.get("meta"), p["value"]["name"])
        result, _ = await self.visit(body_ast, local_env)
        out = []
        for ty in return_ast:
            (tipo, name), _ = await self.visit(ty, local_env)
            if name in result:
                out.append(await self._check(result[name], tipo, ty.get("meta"), name))
        return out[0] if len(out) == 1 else out

    async def visit_call(self, node, env, args=(), kwargs=None):
        name, meta = node.get("name"), node.get("meta")
        ast_args   = [(await self.visit(a, env))[0] for a in node.get("args", [])]
        ast_kwargs = {k: (await self.visit(v, env))[0] for k,v in node.get("kwargs",{}).items()}
        all_args, all_kwargs = list(args) + ast_args, {**(kwargs or {}), **ast_kwargs}
        fn = scheme.get(env, str(name))
        if callable(fn):
            result = await fn(*all_args, **all_kwargs) \
                     if asyncio.iscoroutinefunction(fn) else fn(*all_args, **all_kwargs)
        elif isinstance(fn, tuple) and len(fn) == 3:
            result = await self._call_dsl_fn(fn, all_args, all_kwargs)
        else:
            raise DSLRuntimeError(f"Funzione sconosciuta: '{name}'", meta)
        return result, env

    async def invoke(self, fn, args=(), kwargs=None):
        """Esegue una funzione dall'esterno del DAG — unico uso lecito di flow.act."""
        if callable(fn):            s = flow.step(fn, *args, **(kwargs or {}))
        elif isinstance(fn, tuple): s = flow.step(self._call_dsl_fn, fn, args, kwargs or {})
        else:                       raise DSLRuntimeError("Funzione sconosciuta")
        return await flow.act(s)

    async def _check(self, value, expected, meta, name):
        if expected in CUSTOM_TYPES:
            return await scheme.normalize(value, CUSTOM_TYPES[expected])
        py = TYPE_MAP.get(expected)
        if py and not (isinstance(value, py) and not (py is int and isinstance(value, bool))):
            raise DSLRuntimeError(
                f"Tipo errato '{name}': atteso {expected}, ottenuto {type(value).__name__}", meta)
        return value

    async def resolve(self, val, env):
        while callable(val):
            res = val(**env); val = await res if inspect.isawaitable(res) else res
        return val

# ============================================================================
# ============================================================================
# ============================================================================
# DAG GENERATOR
# ============================================================================
#
# Responsabilità unica: ordinare le dichiarazioni top-level del DSL
# e eseguirle in parallelo quando le dipendenze lo permettono.
#
# Il contesto nested è l'unica struttura dati — lo stesso env che usa
# l'Interpreter. Ogni nodo legge da env e scrive il suo risultato in env.
# Nessuna conversione flat↔nested, nessuna funzione di supporto.
#
#   exports: { "resource": imports.load.resource }   deps: [imports]
#   imports: { 'load': resource("load.py") }         deps: []
#   aaa: imports.load |> print("###")                deps: [imports]
#
# I dict top-level NON vengono espansi in sotto-nodi — vengono valutati
# dall'Interpreter intero. Il parallelismo è tra dichiarazioni, non tra
# chiavi di un dict.

class DAGGenerator:

    def __init__(self, env=None):
        self.env     = env or {}
        self._interp = Interpreter()

    # ── analisi statica: nomi e dipendenze ────────────────────────────────────

    @staticmethod
    def _keys(node) -> list:
        """Nomi definiti da un item AST."""
        if not isinstance(node, dict): return []
        t = node.get("type")
        if t == "declaration": return DAGGenerator._keys(node.get("target"))
        if t == "pair":
            k, v = node.get("key", {}), node.get("value", {})
            if v.get("type") in ("var","identifier") and k.get("type") in ("var","identifier"):
                return [v["name"]]
            kn = k.get("value") if k.get("type") == "string" else k.get("name")
            return [kn] if kn else []
        if t in ("var","identifier"): return [node["name"]]
        if t in ("sequence","tuple","list","dictionary_node","dict"):
            return [k for x in node.get("items",[]) for k in DAGGenerator._keys(x)]
        return []

    @staticmethod
    def _deps(node) -> set:
        """Radici top-level referenziate da un nodo AST."""
        _LEAF   = frozenset({"number","string","bool","any"})
        _OPAQUE = frozenset({"function_def","function_value"})
        _SKIP   = frozenset({"meta","type","op"})
        if isinstance(node, (list, tuple)):
            return set().union(*(DAGGenerator._deps(x) for x in node))
        if isinstance(node, dict):
            t = node.get("type")
            if t in ("var","identifier"):  return {node["name"].split(".")[0]}
            if t == "context_var":         return set()
            if t in _LEAF or t in _OPAQUE: return set()
            return set().union(*(DAGGenerator._deps(v) for k,v in node.items()
                                 if k not in _SKIP))
        return set()

    # ── compilazione ─────────────────────────────────────────────────────────

    def compile(self, ast) -> list:
        """AST → lista di flow.node() con dipendenze tra dichiarazioni top-level."""
        items   = ast.get("items", [])
        defined = {k for item in items for k in self._keys(item)}

        nodes = []
        for item in items:
            ks   = self._keys(item)
            if not ks: continue
            vn   = item.get("value", item)
            deps = [d for d in self._deps(vn) if d in defined and d not in ks]

            if len(ks) == 1:
                def _w(it=item, name=ks[0]):
                    async def w(env):
                        (key, val), _ = await self._interp.visit(it, env)
                        return val if not isinstance(key, tuple) else dict(zip(key, val))
                    return w
                nodes.append(flow.node(ks[0], _w(), deps=deps))
            else:
                # multi-variabile: a, b := expr
                grp = "_grp_" + "_".join(ks)
                def _gw(it=item):
                    async def w(env):
                        (key, val), _ = await self._interp.visit(it, env)
                        return dict(zip(key, val)) if isinstance(key, tuple) else val
                    return w
                nodes.append(flow.node(grp, _gw(), deps=deps))
                for k in ks:
                    def _ex(key=k, g=grp):
                        async def ex(env): return (flow._get_nested(env, g) or {}).get(key)
                        return flow.node(key, ex, deps=[g])
                    nodes.append(_ex())
        return nodes

    async def run(self, ast):
        nodes = self.compile(ast)
        if not nodes:
            async def _root(env):
                result, _ = await self._interp.visit(ast, env)
                return result
            nodes = [flow.node("__result__", _root)]
        return await flow.run(nodes, env=self.env)

# PUBLIC API
# ============================================================================

def create_parser():
    return Lark(GRAMMAR, parser='lalr', propagate_positions=True)

def parse(source: str, parser: Lark) -> dict:
    return DSLTransformer().transform(parser.parse(source))

async def execute(source_or_ast, parser, functions):
    ast = parse(source_or_ast, parser) if isinstance(source_or_ast, str) else source_or_ast
    return await DAGGenerator(functions).run(ast)