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

function_call: identifier "(" [sequence] ")"
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
QUALIFIED_CNAME: CNAME ("." (CNAME|INT|"*"))+
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
    'transform': scheme.transform,
    'get': scheme.get,
    'normalize': scheme.normalize,
    'put': scheme.put,
    'format': scheme.format,
    'foreach': flow.foreach,
    'retry': flow.retry,
    'convert': scheme.convert,
    'keys': lambda d: list(d.keys()) if isinstance(d, dict) else [],
    'values': lambda d: list(d.values()) if isinstance(d, dict) else [],
    'print': lambda *inputs: (print(*inputs), inputs)[1],
    'pass': lambda *inputs: inputs,
    'assert': flow.assertt,
    'guard': flow.guard,
    'when': flow.when,
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
            #print("#ITEM#",input)
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
    def __init__(self, message, meta=None):
        if meta:
            start_line = meta.get("line", None)
            start_col = meta.get("column", None)
            end_line = meta.get("end_line", None)
            end_col = meta.get("end_column", None)

            if start_line is not None and start_col is not None:
                if end_line is not None and end_col is not None:
                    message = f"{message} (line {start_line}:{start_col} - {end_line}:{end_col})"
                else:
                    message = f"{message} (line {start_line}, col {start_col})"
        super().__init__(message)

class Interpreter:
    def __init__(self, env=None):
        self.env = env if env is not None else {}
        self._node_stack = []

    # =========================================================
    # ENTRY POINT
    # =========================================================
    @flow.action()
    async def run(self, ast, **c):
        value, _ = await self.visit(ast, self.env)
        return value

    # =========================================================
    # DISPATCHER (VISIT)
    # =========================================================
    async def visit(self, node, env):
        if not isinstance(node, dict):
            return node, env

        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)

        if not method:
            raise DSLRuntimeError(f"Unknown node type: {t}", node.get("meta"))

        self._node_stack.append(node)
        try:
            # Esecuzione tramite il framework flow
            res = await flow.act(flow.step(method, node, env))
            
            if isinstance(res, dict) and res.get('errors'):
                raise DSLRuntimeError(res['errors'][0])

            # Ritorna gli output (valore, ambiente)
            return res.get('outputs')

        except DSLRuntimeError as e:
            trace = " -> ".join(
                f"{n.get('type')}({n.get('meta', {}).get('line','?')}:{n.get('meta', {}).get('column','?')})"
                for n in self._node_stack
            )
            e.args = (f"{e.args[0]} | Stack trace: {trace}",)
            raise
        finally:
            self._node_stack.pop()

    async def resolve(self, val, env):
        # Se è un'istanza di LazyBinOp o ContextVar, le eseguiamo
        while callable(val):
            # Invochiamo il callable passando l'ambiente come contesto
            res = val(**env)
            # Se il risultato è una coroutine, la attendiamo
            if inspect.isawaitable(res):
                val = await res
            else:
                val = res
        return val

    # =========================================================
    # PRIMITIVES & IDENTIFIERS
    # =========================================================
    async def visit_number(self, node, env): return node["value"], env
    async def visit_string(self, node, env): return node["value"], env
    async def visit_bool(self, node, env):   return node["value"], env
    async def visit_any(self, node, env):    return None, env
    async def visit_identifier(self, node, env):return node["name"], env
    async def visit_var(self, node, env):
        name = node["name"]
        val = scheme.get(env, name, name)
        return val, env
    async def visit_context_var(self, node, env):
        name = node["name"]
        
        # Restituiamo una funzione che accetta (received, expected)
        # Questa funzione si chiude sopra il 'name' e lo usa per la logica
        async def closure(*data,**data_context):
            #result, _ = await self.visit(node, data_context)
            #print("#####>",name,type(data_context),data_context)
            '''if not isinstance(data_context, dict):
                return data_context'''
            
            return scheme.get(data_context, name)
        
        #return closure, env
        return ContextVar(name), env
    async def visit_function_def(self, node, env):

        # ----------------------
        # PARAMETRI
        # ----------------------
        params = []

        '''for p in node["params"]:
            # se è typed_var (dopo che sistemi la grammar)
            if p.get("type") == "typed_var":
                params.append({
                    "var_type": p["var_type"],
                    "name": p["name"]
                })
            else:
                # fallback temporaneo per il tuo AST attuale
                # dict con pair(int:c)
                pair = p["items"][0]
                params.append(pair)'''

        # ----------------------
        # BODY
        # ----------------------
        body_value = node["body"]

        # ----------------------
        # RETURN TYPE
        # ----------------------
        '''return_types = []
        for r in node["return_type"].get("items",node["return_type"]):
            print(r)
            pair = r["items"][0]
            return_types.append(pair)'''
        params = node["params"].get("items",[node["params"]])
        return_type = node["return_type"].get("items",[node["return_type"]])

        return (params, body_value, return_type), env

    # =========================================================
    # DECLARATIONS (MULTIPLE & SINGLE)
    # =========================================================
    
    async def visit_declaration(self, node, env):
        val, _ = await self.visit(node["value"], env)
        key, _ = await self.visit(node["target"], env)
        meta = node.get("meta")
        #print("BOOOOOOOOOOOOM",node["target"])
        items = key if isinstance(key[0],tuple) else [key]
        keys = []
        values = []
        #print(key)
        if node["target"]["type"] == "pair":
            tipo = node["target"]["key"]["name"]
            decl_type, name = key
            if decl_type == 'type':
                CUSTOM_TYPES[name] = val
                return (name, val), env
            checked_val = await self._check_type(val, tipo, meta, name)
            return (name, checked_val), env
            #return (name,val),env


        for i,t in enumerate(items):
            tipo = node["target"]["items"][i]["key"]["name"]
            decl_type, name = t
            if decl_type == "type":
                CUSTOM_TYPES[name] = val
            
            keys.append(name)
            if isinstance(val,tuple):
                checked_val = await self._check_type(val[i], tipo, meta, name)
                values.append(checked_val)
            else:
                checked_val = await self._check_type(val, tipo, meta, name)
                values.append(checked_val)
        return (tuple(keys), tuple(values)), env
        # Assumiamo che node["target"] contenga la definizione (tipo, nome)
        '''for t in node["target"]:
            tu, _ = await self.visit(t, {})
            decl_type, name = tu[0], tu[1]

            # Gestione Tipi Personalizzati
            if decl_type == "type":
                CUSTOM_TYPES[name] = val
                return (name, val), env # Restituisce il nome del tipo e la sua struttura

            # Gestione Destrutturazione (se tu[0] è una tupla di coppie tipo/nome)
            if isinstance(decl_type, tuple):
                keys = [i[0] for i in tu]
                vals = [await self._check_type(val[idx], i[0], meta, i[1]) for idx, i in enumerate(tu)]
                return (tuple(keys), tuple(vals)), env

            # Gestione Variabile Singola Standard
            checked_val = await self._check_type(val, decl_type, meta, name)
            return (key, checked_val), env'''

    # =========================================================
    # COLLECTIONS
    # =========================================================
    async def visit_dict(self, node, env):
        result = {}

        for item in node["items"]:
            evaluation_env = env | result
            res, _ = await self.visit(item, evaluation_env)
            #if item['type'] == 'pair':
            #print(f"##### res: {res}")
            #print(f"##### type: {type(res)}")
            key, value = res
            #print("##### pair", key, value)
            if isinstance(key, tuple) and isinstance(value, tuple) and len(key) == len(value):
                for i,k in enumerate(key):
                    result[key[i]] = value[i]
            else:
                result[key] = value
        #print("##### dict", result)
        return result, env
    
    async def visit_pair(self, node, env):
        # Utilizzato sia per i dati {k:v} che per i tipi int:x
        key, _ = await self.visit(node["key"], env) 
        value, _ = await self.visit(node["value"], env)
        #if not isinstance(key, (str, int, float, tuple, LazyBinOp,type)):
        #    raise DSLRuntimeError(f"Key invalida: {key}:{value}. Deve essere un tipo primitivo.", node.get("meta"))
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
        # 1. Risolviamo i valori dei due rami
        left, env = await self.visit(node["left"], env)
        right, env = await self.visit(node["right"], env)
        op = node["op"]
        if isinstance(left, tuple):
            left = left[0]
        
        if isinstance(right, tuple):
            right = right[0]

        l_desc = repr(left)
        r_desc = repr(right)
        espressione_totale = f"{l_desc} {op} {r_desc}"

        # 2. Gestione Lazy (se uno dei due è una closure/context_var)
        if callable(left) or callable(right):
            def lazy_binop(*a, **context):
                l = left(**context) if callable(left) else left
                r = right(**context) if callable(right) else right
                # Usiamo OPS_FUNCTIONS che hai già definito in alto nel file
                # Mappando l'operatore DSL alla chiave corretta (es. "and" -> "OP_AND")
                op_key = f"OP_{OPS_MAP.get(op, op.upper())}"
                return OPS_FUNCTIONS[op_key](l, r)
            return LazyBinOp(lazy_binop, espressione_totale), env
            #return lazy_binop, env

        # 3. Valutazione immediata (Standard)
        # Mappa pulita per evitare KeyError
        logic_ops = {
            "and": lambda: left and right,
            "or":  lambda: left or right,
            "==":  lambda: left == right,
            "!=":  lambda: left != right,
            ">":   lambda: left > right,
            "<":   lambda: left < right,
            ">=":  lambda: left >= right,
            "<=":  lambda: left <= right,
            "+":   lambda: left + right,
            "-":   lambda: left - right,
            "*":   lambda: left * right,
            "/":   lambda: left / right,
            "%":   lambda: left % right,
            "^":   lambda: left ** right,
        }

        try:
            # Se l'operatore non è in logic_ops, prova a cercarlo in OPS_MAP
            operation = logic_ops.get(op)
            if not operation:
                # Fallback su OPS_FUNCTIONS usando la tua OPS_MAP
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

    async def _call_function(self, function,args=[],kwargs={}):
        local_env = {}
        
        #name = node["name"]
        params_ast, body_ast, return_ast = function
        # Bind parametri
        for param_node, arg_node in zip(params_ast, args):
            param_type = param_node["key"]["name"]
            param_name = param_node["value"]["name"]
            arg_value = await self._check_type(arg_node, param_type, param_node.get("meta"), param_name)
            local_env[param_name] = arg_value
        # Esegui body
        result, _ = await self.visit(body_ast, local_env)
        out = []
        # Controllo tipo di ritorno
        for ty in return_ast:
            pair,env = await self.visit(ty,local_env)
            tipo,name = pair
            if name in result:
                out.append(await self._check_type(result[name], tipo, ty.get("meta"),name))

        if len(out) == 1:
            return out[0]

        return out

    async def visit_call(self, node, env, args=[], kwargs={}):
        name,meta = node.get("name"),node.get("meta")

        # Risoluzione argomenti aggiuntivi dal nodo AST
        ast_args = [(await self.visit(a, env))[0] for a in node.get("args", [])]
        all_args = list(args) + ast_args
        
        ast_kwargs = {k: (await self.visit(v, env))[0] for k, v in node.get("kwargs", {}).items()}
        all_kwargs = {**kwargs, **ast_kwargs}
        
        function = scheme.get(env, str(name))
        
        if callable(function):
            step = flow.step(function,*all_args,**all_kwargs)
        elif isinstance(function, tuple) and len(function) == 3:
            #params_ast, body_ast, return_ast = function
            fn = scheme.get(env,name)
            step = flow.step(self._call_function,fn,all_args,all_kwargs)
        else:
            raise DSLRuntimeError(f"Unknown function '{name}'", meta)

        action = await flow.act(step)
        #print("####1",action)
        output = action["outputs"]
        #print("####2",output)
        return output, env

    async def invoke(self, function, args=[], kwargs={}):
        """
        Punto di ingresso universale per eseguire funzioni.
        'target' può essere:
        - Una stringa (nome della funzione nel dizionario env)
        - Una funzione Python reale
        - Un oggetto 'function' del DSL
        """
        
        if callable(function):
            step = flow.step(function,*args,**kwargs)
        elif isinstance(function, tuple) and len(function) == 3:
            step = flow.step(self._call_function,function,args,kwargs)
        else:
            raise DSLRuntimeError(f"Unknown function ")

        action = await flow.act(step)
        return action.get("outputs",action)
        

    async def _check_type(self, value, expected_type, meta, var_name):
        py_type = TYPE_MAP.get(expected_type)
        
        if expected_type in CUSTOM_TYPES:
            return value # Gestione tipi custom semplificata
        
        if py_type:
            # Python considera bool come una sottoclasse di int, quindi isinstance(True, int) == True. 
            # Dobbiamo prevenire esplicitamente questa sovrapposizione.
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

@flow.action()
def parse(content: str, parser: Lark,**data):
    return DSLTransformer().transform(parser.parse(content))

@flow.action()
async def execute(content_or_ast, parser, functions):
    ast = parse(content_or_ast, parser) if isinstance(content_or_ast, str) else content_or_ast
    return await Interpreter(functions).run(ast)