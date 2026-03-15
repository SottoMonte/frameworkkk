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
# DAG GENERATOR — Analisi statica dell'AST e generazione nodi flow
# ============================================================================

class DAGGenerator:
    """Legge un AST root-dict e genera una lista di flow.node() per flow.run(), oppure esegue AST puro."""

    def __init__(self, env=None):
        self.env = env if env is not None else {}
        self._node_stack = []

    # --- Analisi statica: estrae le chiavi definite da un item AST ---
    def keys(self, node):
        if not isinstance(node, dict): return []
        t = node.get("type")
        if t == "declaration": return self.keys(node.get("target"))
        if t == "pair":
            k, v = node.get("key", {}), node.get("value", {})
            # pattern TIPO:NOME (es. int:x, type:MyType) o NOME:VALORE
            if v.get("type") in ("var", "identifier") and k.get("type") in ("var", "identifier"):
                return [v["name"]]
            # pattern CHIAVESTRINGA:VALORE (es. 'exports': { ... })
            key_name = k.get("value") if k.get("type") == "string" else k.get("name")
            return [key_name] if key_name else []
            
        if t in ("var", "identifier"): return [node["name"]]
        if t in ("sequence", "tuple", "list", "dictionary_node", "dict"):
            return [k for x in node.get("items", []) for k in self.keys(x)]
        return []

    # --- Analisi statica: estrae le dipendenze (variabili usate) ---
    def deps(self, node):
        if isinstance(node, (list, tuple)):
            return set().union(*(self.deps(x) for x in node))
        if isinstance(node, str):
            return {node.split(".")[0]}
        if isinstance(node, dict):
            t = node.get("type")
            if t in ("var", "identifier"):
                return {node["name"].split(".")[0]}
            if t == "context_var":
                return set()
            return set().union(*(self.deps(v) for k, v in node.items() if k not in ("meta", "type")))
        return set()

    # --- Pulisce l'output del DAG, estraendo solo gli outputs ---
    @staticmethod
    def _is_flow_result(v):
        """Un risultato flow ha il marker __flow__."""
        return isinstance(v, dict) and v.get("__flow__")

    @staticmethod
    def clean(ctx):
        if not isinstance(ctx, dict): return ctx
        return {
            k: (v["outputs"] if DAGGenerator._is_flow_result(v) else v)
            for k, v in ctx.items()
        }

    # --- Genera nodi DAG da un AST root-dict ---
    def generate(self, ast, env):
        items = ast.get("items", [])
        defined = {k for item in items for k in self.keys(item)}
        nodes = []

        for item in items:
            item_keys = self.keys(item)
            if not item_keys: continue

            value_node = item.get("value", item)
            item_deps = [d for d in self.deps(value_node) if d in defined and d not in item_keys]

            # Factory: cattura variabili nel closure
            def make_worker(ast_item):
                async def worker(**kw):
                    local_env = env | kw
                    res, _ = await self.visit(ast_item, local_env)
                    key, value = res
                    if isinstance(key, tuple) and isinstance(value, tuple):
                        return dict(zip(key, value))
                    return value
                return worker

            if len(item_keys) == 1:
                nodes.append(flow.node(item_keys[0], make_worker(item), deps=item_deps))
            else:
                # Multi-variabile: nodo gruppo + estrattori
                group = "_grp_" + "_".join(item_keys)
                nodes.append(flow.node(group, make_worker(item), deps=item_deps))
                for k in item_keys:
                    def make_extract(key, grp=group):
                        async def extract(**kw):
                            g = kw.get(grp)
                            return g[key] if isinstance(g, dict) else g
                        return extract
                    nodes.append(flow.node(k, make_extract(k), deps=[group]))

        return nodes

    # ============================================================================
    # EXECUTION ENGINE
    # ============================================================================

    async def run(self, ast):
        # Prova prima a generare un DAG (se l'AST è un dizionario root)
        nodes = self.generate(ast, self.env)
        if nodes:
            return await flow.run(nodes)
        
        # Altrimenti, valutazione AST pura sequenziale
        result, _ = await self.visit(ast, self.env)
        return result

    async def visit(self, node, env):
        if not isinstance(node, dict):
            return node, env
        
        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)
        if not method:
            raise DSLRuntimeError(f"Unknown node type: {t}", node.get("meta"))
        
        self._node_stack.append(node)
        try:
            # Eseguiamo tramite flow.act per avere monitoraggio e cattura errori
            res = await flow.act(flow.step(method, node, env))
            
            if isinstance(res, dict) and res.get('success') is False:
                # Errore logico o eccezione durante l'esecuzione dello step
                raise DSLRuntimeError(res['errors'][0])
            
            return res.get('outputs')
        except DSLRuntimeError as e:
            # Arricchisce lo stack trace con le info dei nodi AST
            trace = " -> ".join(
                f"{n.get('type')}({n.get('meta', {}).get('line','?')}:{n.get('meta', {}).get('column','?')})"
                for n in self._node_stack
            )
            e.args = (f"{e.args[0]} | Stack trace: {trace}",)
            raise
        finally:
            self._node_stack.pop()

    async def resolve(self, val, env):
        while callable(val):
            res = val(**env)
            val = await res if inspect.isawaitable(res) else res
        return val

    # =========================================================
    # VISITOR METHODS
    # =========================================================

    async def visit_number(self, node, env): return node["value"], env
    async def visit_string(self, node, env): return node["value"], env
    async def visit_bool(self, node, env):   return node["value"], env
    async def visit_any(self, node, env):    return None, env
    async def visit_identifier(self, node, env): return node["name"], env
    async def visit_var(self, node, env):
        return scheme.get(env, node["name"], node["name"]), env
    async def visit_context_var(self, node, env):
        return ContextVar(node["name"]), env
    async def visit_function_def(self, node, env):
        params = node["params"].get("items", [node["params"]])
        return_type = node["return_type"].get("items", [node["return_type"]])
        return (params, node["body"], return_type), env

    # =========================================================
    # DECLARATIONS & COLLECTIONS
    # =========================================================
    async def visit_declaration(self, node, env):
        val, _ = await self.visit(node["value"], env)
        key, _ = await self.visit(node["target"], env)
        meta = node.get("meta")
        items = key if isinstance(key[0], tuple) else [key]
        
        if node["target"]["type"] == "pair":
            tipo = node["target"]["key"]["name"]
            name = node["target"]["value"]["name"]
            if tipo == 'type':
                CUSTOM_TYPES[name] = val
                return (name, val), env
            checked_val = await self._check_type(val, tipo, meta, name)
            return (name, checked_val), env
            
        keys, values = [], []
        for i, t in enumerate(items):
            tipo = node["target"]["items"][i]["key"]["name"]
            name = node["target"]["items"][i]["value"]["name"]
            if tipo == "type":
                CUSTOM_TYPES[name] = val
            keys.append(name)
            checked_val = await self._check_type(
                val[i] if isinstance(val, tuple) else val, tipo, meta, name
            )
            values.append(checked_val)
        return (tuple(keys), tuple(values)), env

    async def visit_dict(self, ast, env):
        result = {}
        for item in ast["items"]:
            # Valutazione sequenziale con propagazione dei risultati precedenti
            res, _ = await self.visit(item, env | result)
            key, value = res
            # Se la chiave è un tuple (es. int:x) usiamo il secondo elemento (x)
            if isinstance(key, tuple) and not isinstance(value, tuple):
                if len(key) == 2: key = key[1]
                
            if isinstance(key, tuple) and isinstance(value, tuple):
                result.update(zip(key, value))
            else:
                result[key] = value
        return result, env

    async def visit_pair(self, node, env):
        value, _ = await self.visit(node["value"], env)
        if node["key"]["type"] == "var":
            key = node["key"]["name"]
        else:
            key, _ = await self.visit(node["key"], env)
        return (key, value), env

    async def visit_tuple(self, node, env):
        items = []
        for item in node["items"]:
            val, env = await self.visit(item, env)
            items.append(val)
        return tuple(items), env

    async def visit_sequence(self, node, env):
        items = []
        for item in node["items"]:
            val, env = await self.visit(item, env)
            items.append(val)
        return tuple(items), env

    async def visit_list(self, node, env):
        items = []
        for item in node["items"]:
            val, env = await self.visit(item, env)
            items.append(val)
        return items, env

    # =========================================================
    # LOGIC & MATH
    # =========================================================

    async def visit_binop(self, node, env):
        left, env = await self.visit(node["left"], env)
        right, env = await self.visit(node["right"], env)
        op = node["op"]
        
        if isinstance(left, tuple): left = left[0]
        if isinstance(right, tuple): right = right[0]

        # Gestione Lazy
        if callable(left) or callable(right):
            def lazy_binop(*a, **context):
                l = left(**context) if callable(left) else left
                r = right(**context) if callable(right) else right
                op_key = f"OP_{OPS_MAP.get(op, op.upper())}"
                return OPS_FUNCTIONS[op_key](l, r)
            return LazyBinOp(lazy_binop, f"{repr(left)} {op} {repr(right)}"), env

        # Valutazione immediata
        logic_ops = {
            "and": lambda: left and right, "or":  lambda: left or right,
            "==":  lambda: left == right,  "!=":  lambda: left != right,
            ">":   lambda: left > right,   "<":   lambda: left < right,
            ">=":  lambda: left >= right,  "<=":  lambda: left <= right,
            "+":   lambda: left + right,   "-":   lambda: left - right,
            "*":   lambda: left * right,   "/":   lambda: left / right,
            "%":   lambda: left % right,   "^":   lambda: left ** right,
        }

        try:
            operation = logic_ops.get(op)
            if not operation:
                op_key = f"OP_{OPS_MAP.get(op)}"
                return OPS_FUNCTIONS[op_key](left, right), env
            return operation(), env
        except Exception as e:
            raise DSLRuntimeError(f"Errore nell'operazione '{op}': {str(e)}", node.get("meta"))

    async def visit_not(self, node, env):
        val, env = await self.visit(node["value"], env)
        return not val, env

    # =========================================================
    # PIPE & CALLS
    # =========================================================
    async def visit_pipe(self, node, env):
        steps = node["steps"]
        val, env = await self.visit(steps[0], env)
        for step in steps[1:]:
            val, env = await self.visit_call(step, env, args=[val])
        return val, env

    async def _call_function(self, function, args=[], kwargs={}):
        params_ast, body_ast, return_ast = function
        local_env = {}
        for param_node, arg_node in zip(params_ast, args):
            param_type = param_node["key"]["name"]
            param_name = param_node["value"]["name"]
            arg_value = await self._check_type(arg_node, param_type, param_node.get("meta"), param_name)
            local_env[param_name] = arg_value
            
        result, _ = await self.visit(body_ast, local_env)
        out = []
        for ty in return_ast:
            pair, _ = await self.visit(ty, local_env)
            tipo, name = pair
            if name in result:
                out.append(await self._check_type(result[name], tipo, ty.get("meta"), name))

        return out[0] if len(out) == 1 else out

    async def visit_call(self, node, env, args=[], kwargs={}):
        name, meta = node.get("name"), node.get("meta")
        ast_args = [(await self.visit(a, env))[0] for a in node.get("args", [])]
        all_args = list(args) + ast_args
        ast_kwargs = {k: (await self.visit(v, env))[0] for k, v in node.get("kwargs", {}).items()}
        all_kwargs = {**kwargs, **ast_kwargs}
        
        function = scheme.get(env, str(name))
        if callable(function):
            step = flow.step(function, *all_args, **all_kwargs)
        elif isinstance(function, tuple) and len(function) == 3:
            step = flow.step(self._call_function, function, all_args, all_kwargs)
        else:
            raise DSLRuntimeError(f"Unknown function '{name}'", meta)

        action = await flow.act(step)
        return action.get("outputs"), env

    async def invoke(self, function, args=[], kwargs={}):
        if callable(function):
            step = flow.step(function, *args, **kwargs)
        elif isinstance(function, tuple) and len(function) == 3:
            step = flow.step(self._call_function, function, args, kwargs)
        else:
            raise DSLRuntimeError(f"Unknown function")

        return await flow.act(step)

    async def _check_type(self, value, expected_type, meta, var_name):
        py_type = TYPE_MAP.get(expected_type)
        if expected_type in CUSTOM_TYPES:
            return await scheme.normalize(value, CUSTOM_TYPES[expected_type])
        
        if py_type:
            is_valid = isinstance(value, py_type) and not (py_type is int and isinstance(value, bool))
            if not is_valid:
                raise DSLRuntimeError(
                    f"Type error for '{var_name}': expected {expected_type}, got {type(value).__name__}", 
                    meta
                )
        return value
        '''if isinstance(expected_type,dict):
            #chiave = next(k for k, v in CUSTOM_TYPES.items() if v == expected_type)
            #print(chiave)
            return value # Gestione tipi custom semplificata
        
        is_valid = isinstance(value, expected_type) and not (expected_type is int and isinstance(value, bool))
            
        if not is_valid:
            print(value)
            raise DSLRuntimeError(
                    f"Type error for '{var_name}': expected {expected_type}, got {type(value).__name__}", 
                    meta
                )
        return value'''

# ============================================================================
# PUBLIC API (NO GLOBAL PARSER)
# ============================================================================

def create_parser():
    return Lark(GRAMMAR, parser='lalr', propagate_positions=True)

def parse(content: str, parser: Lark,**data):
    return DSLTransformer().transform(parser.parse(content))

async def execute(content_or_ast, parser, functions):
    ast = parse(content_or_ast, parser) if isinstance(content_or_ast, str) else content_or_ast
    return await DAGGenerator(functions).run(ast)