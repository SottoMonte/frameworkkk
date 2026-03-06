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


# ============================================================================
# GRAMMAR
# ============================================================================

GRAMMAR = r"""
// ==========================================
// PUNTO DI INGRESSO (ROOT)
// ==========================================
start: dictionary

// ==========================================
// STRUTTURE DATI (DIZIONARI E ITEM)
// ==========================================
dictionary: "{" [item (";" item)* ";"?] "}" -> dictionary_node

item: sequence ":=" sequence -> declaration
    | sequence

?sequence: expr ("," expr)* -> tuple_node

?expr: pipe
     | expr ":" expr -> pair

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

?atom: value
     | identifier
     | tuple
     | list
     | dictionary
     | function_call

tuple: "(" [sequence] ")" -> tuple_node
list: "[" [sequence] "]" -> list_node

identifier: CNAME -> identifier | QUALIFIED_CNAME -> identifier

function_call: identifier "(" [sequence] ")"

value: SIGNED_NUMBER      -> number
     | STRING             -> string
     | "true"i            -> true
     | "false"i           -> false
     | "*"                -> any_val

PIPE: "|>"
COMPARISON_OP: "==" | "!=" | ">=" | "<=" | ">" | "<"
ARITHMETIC_OP: "+" | "-" | "*" | "/" | "%"
STRING: ESCAPED_STRING | SINGLE_QUOTED_STRING
SINGLE_QUOTED_STRING: /'[^']*'/
QUALIFIED_CNAME: CNAME ("." CNAME)+

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
    'sentry': flow.sentry,
    'when': flow.when,
}|TYPE_MAP


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

    # -------------------------------------------------
    # VARIABILI / NOMI
    # -------------------------------------------------

    def identifier(self, meta, s):
        # Fondamentale: usiamo "identifier" come tipo per il nome puro
        return self.with_meta({
            "type": "var", 
            "name": str(s[0])
        }, meta)

    def key(self, meta, a):
        # Se arriva un Tree, estrai il token e trasformalo
        if isinstance(a[0], Token):
            return {"type": "var", "name": str(a[0]), "meta": {"line": meta.line, "column": meta.column}}
        return a[0]

    def callable(self, meta, a):
        return a[0]

    # -------------------------------------------------
    # STRUTTURE
    # -------------------------------------------------

    def sequence(self, meta, items):
        # items può contenere un elemento singolo o un'altra sequenza (ricorsione)
        flat_items = []
        for i in items:
            if isinstance(i, dict) and i.get("type") == "tuple":
                flat_items.extend(i["items"])
            else:
                flat_items.append(i)
        
        return self.with_meta({
            "type": "tuple",
            "items": [i for i in flat_items if i is not None]
        }, meta)

    def tuple_node(self, meta, items):
        items = [i for i in items if i is not None]
        
        if len(items) == 1:
            return items[0]
            
        pairs = [i for i, x in enumerate(items) if isinstance(x, dict) and x.get("type") == "pair"]
        
        if len(pairs) == 1 and len(items) > 1:
            idx = pairs[0]
            pair_node = items[idx]
            
            left_part = items[:idx] + [pair_node["key"]]
            right_part = [pair_node["value"]] + items[idx+1:]
            
            left = {"type": "tuple", "items": left_part} if len(left_part) > 1 else left_part[0]
            right = {"type": "tuple", "items": right_part} if len(right_part) > 1 else right_part[0]
            
            return self.with_meta({"type": "pair", "key": left, "value": right}, meta)
            
        if len(items) == 3 and isinstance(items[0], dict) and items[0].get("type") == "tuple" and isinstance(items[1], dict) and items[1].get("type") == "dict" and isinstance(items[2], dict) and items[2].get("type") == "tuple":
            return self.with_meta({
                "type": "function_def",
                "params": items[0].get("items", []),
                "body": items[1],
                "return_type": items[2]
            }, meta)

        return self.with_meta({
            "type": "tuple",
            "items": items
        }, meta)

    def list_node(self, meta, items):
        return self.with_meta({
            "type": "list",
            "items": [i for i in items if i is not None]
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
        print("##############################declaration", a)
        return self.with_meta({
            "type": "declaration",
            "target": a[:-1],
            "value": a[-1]
        }, meta)

    def pair(self, meta, a):
        #print("##############################pair", a)
        return self.with_meta({
            "type": "pair",
            "key": a[0],
            "value": a[1]
        }, meta)

    def item(self, meta, a):
        return a[0]

    # -------------------------------------------------
    # FUNZIONI
    # -------------------------------------------------

    def function_call(self, meta, a):
        fn = a[0]
        args = []
        kwargs = {}

        if len(a) > 1 and a[1] is not None:
            seq = a[1]
            items = seq.get("items", []) if isinstance(seq, dict) and seq.get("type") == "tuple" else [seq]
            for item in items:
                if isinstance(item, dict) and item.get("type") == "pair":
                    key_node = item["key"]
                    key_name = key_node["name"] if isinstance(key_node, dict) and key_node.get("type") == "var" else str(key_node)
                    kwargs[key_name] = item["value"]
                else:
                    args.append(item)
        
        return self.with_meta({
            "type": "call",
            "name": fn,
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
            "right": a[2]
        }, meta)

    def or_op(self, meta, a):
        return self.with_meta({
            "type": "binop",
            "op": "or",
            "left": a[0],
            "right": a[2]
        }, meta)

    def pipe_node(self, meta, items):
        return self.with_meta({
            "type": "pipe",
            "steps": [i for i in items if not isinstance(i, Token)],
        }, meta)

    def start(self, meta, items):
        print(items)
        return items[0]

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

    # =========================================================
    # DECLARATIONS (MULTIPLE & SINGLE)
    # =========================================================
    async def visit_declaration(self, node, env):
        env_after = {} | env
        keys = []
        value, _ = await self.visit(node["value"], env)
        for t in node["target"]:
            tu,_ = await self.visit(t,dict())
            print("############# tu",tu)
            for i in tu:
                if isinstance(i, tuple) and len(i) == 2:
                    keys.append(i[1])
                else:
                    keys = tu
                    return (tu[1],value), env
                print("############# declaration",i)
        print("############# keys",keys)
        
        
        '''for t in pair:
            print("############# BOOM",t)
            key,name = t
            keys.append(name)'''
        '''declared_type,name = target

        if declared_type == "type":
            CUSTOM_TYPES[name] = value
            #env_after[name] = value
            declared_type = 'dict'

        value = await self._check_type(value,declared_type,node.get("meta"),name)
        print("############# declaration",name,value)'''
        return (tuple(keys),value), env

    

    # =========================================================
    # COLLECTIONS
    # =========================================================
    async def visit_dict(self, node, env):
        result = {}

        for item in node["items"]:
            evaluation_env = env | result
            res, _ = await self.visit(item, evaluation_env)
            #if item['type'] == 'pair':
            print(f"##### res: {res}")
            #print(f"##### type: {type(res)}")
            key, value = res
            #print("##### pair", key, value)
            if isinstance(key, tuple) and isinstance(value, tuple) and len(key) == len(value):
                for i,k in enumerate(key):
                    result[key[i]] = value[i]
            else:
                result[key] = value
        print("##### dict", result)
        return result, env
    
    async def visit_pair(self, node, env):
        # Utilizzato sia per i dati {k:v} che per i tipi int:x
        #print("!!!!! pair", node["key"])
        key, _ = await self.visit(node["key"], env) 
        value, _ = await self.visit(node["value"], env) 
        #print("##### pair", key, value)
        # Validazione di sicurezza: le chiavi di un dict devono essere hashable
        if not isinstance(key, (str, int, float, tuple)):
            print("##### key", key,value)
            #raise DSLRuntimeError(f"Key invalida: {type(key)}. Deve essere un tipo primitivo.", node.get("meta"))
            return str(key), env
        return (key, value), env

    async def visit_tuple(self, node, env):
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
        
        try:
            ops = {
                "+": lambda: left + right, "-": lambda: left - right,
                "*": lambda: left * right, "/": lambda: left / right,
                "%": lambda: left % right, "^": lambda: left ** right,
                "==": lambda: left == right, "!=": lambda: left != right,
                ">": lambda: left > right, "<": lambda: left < right,
                ">=": lambda: left >= right, "<=": lambda: left <= right,
                "and": lambda: left and right, "or": lambda: left or right
            }
            return ops[op](), env
        except Exception as e:
            raise DSLRuntimeError(str(e), node.get("meta"))

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

    async def visit_call(self, node, env, args=[], kwargs={}):
        name = node.get("name")
        # Risoluzione argomenti aggiuntivi dal nodo AST
        ast_args = [(await self.visit(a, env))[0] for a in node.get("args", [])]
        all_args = list(args) + ast_args
        
        ast_kwargs = {k: (await self.visit(v, env))[0] for k, v in node.get("kwargs", {}).items()}
        all_kwargs = {**kwargs, **ast_kwargs}
        
        function = scheme.get(env, str(name))
        
        if callable(function):
            action = await flow.act(flow.step(function, *all_args, **all_kwargs))
            return action["outputs"], env
        
        raise DSLRuntimeError(f"Function '{name}' not found or not callable", node.get("meta"))

    async def _check_type(self, value, expected_type, meta, var_name):
        py_type = TYPE_MAP.get(expected_type)
        if expected_type in CUSTOM_TYPES:
            return value # Gestione tipi custom semplificata
        
        if py_type and not isinstance(value, py_type):
            raise DSLRuntimeError(
                f"Type error for '{var_name}': expected {expected_type}, got {type(value).__name__}", 
                meta
            )
        return value

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