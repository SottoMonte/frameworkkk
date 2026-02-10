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
start: dictionary

dictionary: "{" item* "}" | item*
item: pair ";"?

pair: declaration | mapping | function_call

typed_name: type_name ":" CNAME
type_name: CNAME | QUALIFIED_CNAME

declaration: typed_name ":=" expr
mapping: key ":" expr

key: value | typed_name | function_call | CNAME | QUALIFIED_CNAME

?expr: pipe

?pipe: logic (PIPE logic)* -> pipe_node

?logic: comparison
      | "not" logic        -> not_op
      | logic ("and" | "&") logic -> and_op
      | logic ("or"  | "|") logic -> or_op

?comparison: sum
           | comparison COMPARISON_OP sum -> binary_op

?sum: term
    | sum ("+" | "-") term -> binary_op

?term: power
     | term ("*" | "/" | "%") power -> binary_op

?power: atom
      | atom "^" power -> power

?atom: value
     | function_call
     | dictionary
     | tuple
     | list
     | "(" expr ")"
     | typed_name
     | CNAME
     | QUALIFIED_CNAME -> simple_key

tuple: "(" [expr ("," expr)* ","?] ")" -> tuple_
list:  "[" [expr ("," expr)* ","?] "]" -> list_

function_call: callable "(" [call_args] ")"
callable: typed_name | CNAME | QUALIFIED_CNAME

call_args: call_arg ("," call_arg)*
call_arg: expr -> arg_pos
        | CNAME ":" expr -> arg_kw

value: SIGNED_NUMBER        -> number
     | STRING               -> string
     | "true"i              -> true
     | "false"i             -> false
     | "*"                  -> any_val

STRING: ESCAPED_STRING | SINGLE_QUOTED_STRING

PIPE: "|>"
COMPARISON_OP: "==" | "!=" | ">=" | "<=" | ">" | "<"
QUALIFIED_CNAME: CNAME ("." CNAME)+
COMMENT: /#[^\n]*/

%import common.SIGNED_NUMBER
%import common.ESCAPED_STRING
%import common.CNAME
%import common.WS
SINGLE_QUOTED_STRING: /'[^']*'/
%ignore WS
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
    'int': int, 'float': float, 'str': str, 'bool': bool,
    'dict': dict, 'list': list, 'any': object, 'type': dict
}

CUSTOM_TYPES = {}

DSL_FUNCTIONS = {
    'resource': load.resource,
    'transform': scheme.transform,
    'normalize': scheme.normalize,
    'put': scheme.put,
    'format': scheme.format,
    'foreach': flow.foreach,
    #'batch': flow.batch,
    #'parallel': flow.batch,
    #'race': flow.race,
    #'timeout': flow.timeout,
    #'throttle': flow.throttle,
    'retry': flow.retry,
    #'fallback': flow.fallback,
    'keys': lambda d: list(d.keys()) if isinstance(d, dict) else [],
    'values': lambda d: list(d.values()) if isinstance(d, dict) else [],
    'print': lambda d: (print(d), d)[1],
}


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

def unwrap(v):
    return v.get('outputs') if isinstance(v, dict) and 'outputs' in v else v


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

    def simple_key(self, meta, s):
        return self.with_meta({
            "type": "var",
            "name": str(s[0])
        }, meta)

    def type_name(self, meta, a):
        return {
            "type": "type_name",
            "name": str(a[0]),
            "meta": {
                "line": meta.line if hasattr(meta, "line") else None,
                "column": meta.column if hasattr(meta, "column") else None
            }
        }

    def typed_name(self, meta, a):
        
        type_node = a[0]
        name_node = a[1]

        return self.with_meta({
            "type": "typed_var",
            "name": str(name_node),
            "var_type": str(type_node["name"])  # il tipo
        }, meta, fallback=type_node)

    def callable(self, meta, a):
        return a[0]

    # -------------------------------------------------
    # STRUTTURE
    # -------------------------------------------------

    def tuple_(self, meta, items):
        return self.with_meta({
            "type": "tuple",
            "items": items
        }, meta)

    def list_(self, meta, items):
        return self.with_meta({
            "type": "list",
            "items": items
        }, meta)

    def dictionary(self, meta, items):
        return self.with_meta({
            "type": "dict",
            "items": [i for i in items if i is not None]
        }, meta)

    # -------------------------------------------------
    # DICHIARAZIONI / MAPPING
    # -------------------------------------------------

    def declaration(self, meta, a):
        return self.with_meta({
            "type": "declaration",
            "target": a[0],
            "value": a[1]
        }, meta)

    def mapping(self, meta, a):
        return self.with_meta({
            "type": "mapping",
            "key": a[0],
            "value": a[1]
        }, meta)

    def pair(self, meta, a):
        return a[0]

    def item(self, meta, a):
        return a[0]

    # -------------------------------------------------
    # FUNZIONI
    # -------------------------------------------------

    def call_args(self, meta, a):
        return a

    def arg_pos(self, meta, a):
        return ("pos", a[0])

    def arg_kw(self, meta, a):
        return ("kw", str(a[0]), a[1])

    def function_call(self, meta, a):
        fn = a[0]
        args = []
        kwargs = {}

        if len(a) > 1:
            for kind, *data in a[1]:
                if kind == "pos":
                    args.append(data[0])
                else:
                    kwargs[data[0]] = data[1]

        return self.with_meta({
            "type": "call",
            "name": fn["name"],
            "args": args,
            "kwargs": kwargs
        }, meta)

    # -------------------------------------------------
    # ESPRESSIONI
    # -------------------------------------------------

    def binary_op(self, meta, a):
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
            "steps": items
        }, meta)

    # -------------------------------------------------
    # ROOT
    # -------------------------------------------------

    def start(self, meta, items):
        if items:
            return items[0]
        return self.with_meta({
            "type": "dict",
            "items": []
        }, meta)

# ============================================================================
# TRIGGER ENGINE (SEPARATO)
# ============================================================================

class TriggerEngine:

    def __init__(self, visitor):
        self.visitor = visitor
        self.tasks = []

    def register(self, triggers, ctx):
        for trigger, action in triggers:
            if is_call(trigger):
                task = asyncio.create_task(self._event_loop(trigger, action, ctx))
            else:
                task = asyncio.create_task(self._cron_loop(trigger, action, ctx))
            self.tasks.append(task)

    async def _event_loop(self, call_node, action, ctx):
        framework_log("INFO", f"Event listener: {call_node[1]}", emoji="👂")
        while True:
            try:
                result = await self.visitor.visit(call_node, ctx)
                if isinstance(result, dict) and result.get('success'):
                    await self.visitor.visit(action, {**ctx, '@event': result.get('data')})
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)

    async def _cron_loop(self, pattern, action, ctx):
        import datetime
        framework_log("INFO", f"Cron trigger: {pattern}", emoji="⏰")
        while True:
            now = datetime.datetime.now()
            cur = (now.minute, now.hour, now.day, now.month, now.weekday())
            if all(p == '*' or str(p) == str(c) for p, c in zip(pattern, cur)):
                await self.visitor.visit(action, ctx)
            await asyncio.sleep(60 - now.second)

    async def shutdown(self):
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

# ============================================================================
# DSL VISITOR (COMPLETO)
# ============================================================================

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

    def __init__(self, functions=None):
        self.env = {}
        self.functions = functions or {}
        self._node_stack = [] 

    # -------------------------
    # entry
    # -------------------------
    @flow.action()
    async def run(self, ast,**con):
        
        ok = await self.visit(ast)

        return ok

    # -------------------------
    # dispatcher
    # -------------------------

    '''async def visit(self, node):
        if not isinstance(node, dict):
            return node

        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)

        if not method:
            raise DSLRuntimeError(f"Unknown node type: {t}", node.get("meta"))

        #return method(node)
        res = await flow.act(flow.step(method,node))

        if len(res.get('errors')) != 0:
            raise Exception(res.get('errors'))
        
        return res.get('outputs')'''

    async def visit(self, node):
        if not isinstance(node, dict):
            return node

        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)

        if not method:
            raise DSLRuntimeError(f"Unknown node type: {t}", node.get("meta"))

        if not hasattr(self, "_node_stack"):
            self._node_stack = []

        self._node_stack.append(node)
        try:
            res = await flow.act(flow.step(method, node))

            if res.get('errors'):
                # Solleva il primo errore già formattato
                raise DSLRuntimeError(res['errors'][0])

            return res.get('outputs')

        except DSLRuntimeError as e:
            # ricostruisci solo lo stack trace dei nodi, senza ripetere linee
            trace = " -> ".join(
                f"{n.get('type')}({n.get('meta', {}).get('line','?')}:{n.get('meta', {}).get('column','?')})"
                for n in self._node_stack
            )
            # aggiorna il messaggio senza duplicare le linee
            e.args = (f"{e.args[0]} | Stack trace: {trace}",)
            raise
        finally:
            self._node_stack.pop()



    # -------------------------
    # primitives
    # -------------------------

    def visit_number(self, node):
        return node["value"]

    def visit_string(self, node):
        return node["value"]

    def visit_bool(self, node):
        return node["value"]

    def visit_any(self, node):
        return None

    # -------------------------
    # variables
    # -------------------------

    async def _check_type(self, value, expected_type, node_meta=None, var_name=None):
        """
        Controlla e valida il tipo di un valore.
        - Se il tipo è custom, usa validate_type asincrono
        - Altrimenti controlla e converte i tipi standard
        - Genera DSLRuntimeError se il tipo non corrisponde
        """
        # passo 1: validate_type (async) per tipi custom
        if expected_type in CUSTOM_TYPES:
            value = await scheme.normalize(value, CUSTOM_TYPES[expected_type])
            return value

        # passo 2: tipi standard
        py_type = TYPE_MAP.get(expected_type)

        
        # controllo tipo
        if type(value) != py_type:
            raise DSLRuntimeError(
                f"Type error in '{var_name}': expected {expected_type}, got {type(value).__name__}",
                node_meta
            )

        return value

    def visit_var(self, node):
        name = node["name"]
        if name not in self.env:
            raise DSLRuntimeError(f"Undefined variable '{name}'", node.get("meta"))
        return self.env[name]

    def visit_typed_var(self, node):
        # in runtime il tipo è metadata, non influenza il valore
        return self.visit_var({"name": node["name"], "meta": node["meta"]})

    # -------------------------
    # collections
    # -------------------------

    async def visit_tuple(self, node):
        return tuple(await self.visit(i) for i in node["items"])

    async def visit_list(self, node):
        return [await self.visit(i) for i in node["items"]]

    async def visit_dict(self, node):
        result = {}
        for item in node["items"]:
            value = await self.visit(item)

            # item può essere 'declaration' o 'mapping'
            if item["type"] == "declaration":
                key = item["target"]["name"]
                result[key] = value
            elif item["type"] == "mapping":
                key = await self.visit(item["key"])
                result[key] = value

        return result

    # -------------------------
    # declarations / mapping
    # -------------------------

    async def visit_declaration(self, node):
        name = node["target"]["name"]
        value = await self.visit(node["value"])
        declared_type = node["target"].get("var_type")
        value = await self._check_type(value, declared_type, node.get("meta"), name)
        self.env[name] = value
        return value

    async def visit_mapping(self, node):
        key = await self.visit(node["key"])
        value = await self.visit(node["value"])
        self.env[key] = value
        return value

    # -------------------------
    # expressions
    # -------------------------

    async def visit_binop(self, node):
        left = await self.visit(node["left"])
        right = await self.visit(node["right"])
        op = node["op"]

        try:
            if op == "+": return left + right
            if op == "-": return left - right
            if op == "*": return left * right
            if op == "/": return left / right
            if op == "%": return left % right
            if op == "^": return left ** right
            if op == "==": return left == right
            if op == "!=": return left != right
            if op == ">": return left > right
            if op == "<": return left < right
            if op == ">=": return left >= right
            if op == "<=": return left <= right
            if op == "and": return left and right
            if op == "or": return left or right
        except Exception as e:
            raise DSLRuntimeError(str(e), node.get("meta"))

        raise DSLRuntimeError(f"Unsupported operator '{op}'", node.get("meta"))

    async def visit_not(self, node):
        return not await self.visit(node["value"])

    # -------------------------
    # pipe
    # -------------------------

    async def visit_pipe(self, node):
        steps = node["steps"]
        value = await self.visit(steps[0])

        for step in steps[1:]:
            if step["type"] != "call":
                raise DSLRuntimeError(
                    "Pipe expects function calls",
                    step.get("meta")
                )
            value = self._call(step, value)

        return value

    # -------------------------
    # function calls
    # -------------------------

    def visit_call(self, node):
        return self._call(node)

    async def _call(self, node, piped_value=None):
        name = node["name"]

        if name not in self.functions:
            raise DSLRuntimeError(
                f"Unknown function '{name}'",
                node.get("meta")
            )

        fn = self.functions[name]

        args = [await self.visit(a) for a in node["args"]]
        kwargs = {k: await self.visit(v) for k, v in node["kwargs"].items()}

        if piped_value is not None:
            args.insert(0, piped_value)

        try:
            return fn(*args, **kwargs)
        except Exception as e:
            raise DSLRuntimeError(str(e), node.get("meta"))

# ============================================================================
# PUBLIC API (NO GLOBAL PARSER)
# ============================================================================

def create_parser():
    return Lark(GRAMMAR, parser='earley', propagate_positions=True)

@flow.action()
def parse(content: str, parser: Lark,**data):
    return DSLTransformer().transform(parser.parse(content))

@flow.action()
async def execute(content_or_ast, parser, functions):
    ast = parse(content_or_ast, parser) if isinstance(content_or_ast, str) else content_or_ast
    return await Interpreter(functions).run(ast)