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
item: pair ";"? | declaration ";"?
declaration: pair ":=" expr

pair: key ":" expr

key: value | CNAME | QUALIFIED_CNAME

?expr: atom | pipe

?pipe: logic (PIPE logic)* -> pipe_node

?logic: comparison
      | "not" logic        -> not_op
      | logic ("and" | "&") logic -> and_op
      | logic ("or"  | "|") logic -> or_op

?comparison: sum
           | comparison COMPARISON_OP sum -> binary_op

?sum: term
    | sum ARITHMETIC_OP term -> binary_op

?term: power
     | term  power -> binary_op

?power: atom
      | atom "^" power -> power

?atom: tuple|value
     | function_value
     | function_call
     | dictionary
     #| tuple
     #| inline_tuple
     | list
     | "(" expr ")"
     | CNAME -> identifier
     | QUALIFIED_CNAME -> identifier

tuple: "(" [expr ("," expr)* ","?] ")" -> tuple_
inline_tuple: expr ("," expr)+ -> tuple_
list:  "[" [expr ("," expr)* ","?] "]" -> list_

function_call: callable "(" [call_args] ")"
function_value: tuple "," dictionary "," tuple
callable:  CNAME | QUALIFIED_CNAME

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
ARITHMETIC_OP: "+" | "-" | "*" | "/" | "%"
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
    'dict': dict, 'list': list, 'any': object, 'type': dict,
    'function': tuple,

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

    def pair(self, meta, a):
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

    def function_value(self, meta, a):
        params_tuple = a[0]
        body = a[1]
        return_tuple = a[2]

        params = params_tuple["items"] if params_tuple["type"] == "tuple" else []

        return self.with_meta({
            "type": "function_def",
            "params": params,
            "body": body,
            "return_type": return_tuple
        }, meta)

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
            "name": fn,
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

    def __init__(self, env={}):
        self.env = env
        #for key, value in self.functions.items():
        #    self.functions[key] = {'type': 'call', 'name': Token('CNAME', key), 'args': [], 'kwargs': {}, 'meta': {'line': 19, 'column': 17, 'end_line': 19, 'end_column': 19}}
        self._node_stack = [] 

    # =========================================================
    # ENTRY
    # =========================================================
    @flow.action()
    async def run(self, ast,**c):
        value, _ = await self.visit(ast, self.env)
        return value

    # =========================================================
    # DISPATCH
    # =========================================================

    async def visit2(self, node, env):
        if not isinstance(node, dict):
            return node, env

        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)

        if not method:
            raise DSLRuntimeError(
                f"Unknown node type: {t}",
                node.get("meta"),
            )

        return await method(node, env)

    async def visit(self, node, env):
        if not isinstance(node, dict):
            return node, env

        t = node.get("type")
        method = getattr(self, f"visit_{t}", None)

        if not method:
            raise DSLRuntimeError(f"Unknown node type: {t}", node.get("meta"))

        if not hasattr(self, "_node_stack"):
            self._node_stack = []

        self._node_stack.append(node)
        try:
            res = await flow.act(flow.step(method, node,env))

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

    # =========================================================
    # PRIMITIVES
    # =========================================================

    async def visit_number(self, node, env):
        return node["value"], env

    async def visit_string(self, node, env):
        return node["value"], env

    async def visit_bool(self, node, env):
        return node["value"], env

    async def visit_any(self, node, env):
        return None, env

    # =========================================================
    # VARIABLES
    # =========================================================

    async def visit_var(self, node, env):
        name = node["name"]
        
        '''if name not in env:
            raise DSLRuntimeError(
                f"Undefined variable '{name}'",
                node.get("meta")
            )'''

        return scheme.get(env,name,name), env

    async def visit_typed_var(self, node, env):
        return await self.visit_var(
            {"name": node["name"], "meta": node["meta"]},
            env
        )

    # =========================================================
    # DECLARATIONS
    # =========================================================

    async def visit_declaration(self, node, env):
        pair,pass_env = await self.visit(node["target"],dict())

        value, env_after = await self.visit(node["value"], env)
        
        declared_type,name = pair

        if declared_type == "type":
            CUSTOM_TYPES[name] = value
            #env_after[name] = value
            declared_type = 'dict'

        value = await self._check_type(value,declared_type,node.get("meta"),name)

        return (name,value), env_after

    # =========================================================
    # COLLECTIONS
    # =========================================================

    async def visit_pair(self, node, env):
        key, env1 = await self.visit(node["key"], env) 
        value, env2 = await self.visit(node["value"], env1) 
        return (key,value), env1|env2

    async def visit_list(self, node, env):
        items = []
        current_env = env

        for item in node["items"]:
            value, current_env = await self.visit(item, current_env)
            items.append(value)

        return items, current_env

    async def visit_tuple(self, node, env):
        items = []
        current_env = env

        for item in node["items"]:
            value, current_env = await self.visit(item, current_env)
            items.append(value)

        return tuple(items), current_env

    async def visit_dict(self, node, env):
        result = {}

        for item in node["items"]:
            evaluation_env = env | result
            pair, _ = await self.visit(item, evaluation_env)
            key, value = pair
            result[key] = value

        return result, env

    # =========================================================
    # EXPRESSIONS
    # =========================================================

    async def visit_binop(self, node, env):
        left, env1 = await self.visit(node["left"], env)
        right, env2 = await self.visit(node["right"], env1)

        op = node["op"]

        try:
            if op == "+": return left + right, env2
            if op == "-": return left - right, env2
            if op == "*": return left * right, env2
            if op == "/": return left / right, env2
            if op == "%": return left % right, env2
            if op == "^": return left ** right, env2
            if op == "==": return left == right, env2
            if op == "!=": return left != right, env2
            if op == ">": return left > right, env2
            if op == "<": return left < right, env2
            if op == ">=": return left >= right, env2
            if op == "<=": return left <= right, env2
            if op == "and": return left and right, env2
            if op == "or": return left or right, env2

        except Exception as e:
            raise DSLRuntimeError(str(e), node.get("meta"))

        raise DSLRuntimeError(
            f"Unsupported operator '{op}'",
            node.get("meta")
        )

    async def visit_not(self, node, env):
        value, env2 = await self.visit(node["value"], env)
        return not value, env2

    # =========================================================
    # PIPE
    # =========================================================

    async def visit_pipe(self, node, env):
        steps = node["steps"]
        if len(steps) == 1:
            return await self.visit(steps[0], env)
        value, current_env = await self.visit(steps[0], env)
        
        for step in steps[1:]:
            args,kwargs = [value],{}
            if not isinstance(step, dict):
                continue
            
            value, current_env = await self.visit_call(step,current_env,args,kwargs)

        return value, current_env

    # =========================================================
    # CALLS
    # =========================================================
    
    async def _call_function(self, node, env,args=[],kwargs={}):
        local_env = {}
        
        name = node["name"]
        params_ast, body_ast, return_ast = env[name]
        # Bind parametri
        for param_node, arg_node in zip(params_ast, args):
            param_type = param_node["key"]["name"]
            param_name = param_node["value"]["name"]
            arg_value = await self._check_type(arg_node, param_type, param_node.get("meta"), param_name)
            local_env[param_name] = arg_value
        # Esegui body
        result, _ = await self.visit(body_ast, local_env)
        out = None
        # Controllo tipo di ritorno

        for ty in return_ast:
            pair,env = await self.visit(ty,local_env)
            tipo,name = pair
            if name in result:
                out = await self._check_type(result[name], tipo, ty.get("meta"))
        return out   

    async def visit_call(self, node, env, args=[], kwargs={}):
        name, meta = node.get("name"), node.get("meta")
        args = args + [(await self.visit(a, env))[0] for a in node.get("args",[])]
        kwargs = {k: (await self.visit(v, env))[0] for k, v in kwargs.items()}
        function = scheme.get(env,str(name))
        
        if callable(function):
            step = flow.step(function,*args,**kwargs)
        elif isinstance(function, tuple) and len(function) == 3:
            #params_ast, body_ast, return_ast = function
            step = flow.step(self._call_function,node,env,args,kwargs)
        else:
            raise DSLRuntimeError(f"Unknown function '{name}'", meta)

        action = await flow.act(step)
        #print("####1",action)
        output = action["outputs"]
        #print("####2",output)
        return output, env

    # =========================================================
    # TYPE CHECK
    # =========================================================

    async def visit_function_def2(self, node, env):
        # Una funzione è un valore già pronto
        return node, env

    async def visit_function_def(self, node, env):

        # ----------------------
        # PARAMETRI
        # ----------------------
        params = []

        for p in node["params"]:
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
                params.append(pair)

        # ----------------------
        # BODY
        # ----------------------
        body_value = node["body"]

        # ----------------------
        # RETURN TYPE
        # ----------------------
        return_types = []

        for r in node["return_type"]["items"]:
            pair = r["items"][0]
            return_types.append(pair)

        return (params, body_value, return_types), env

    async def _check_type(self, value, expected_type, meta=None, var_name=None):
        py_type = TYPE_MAP.get(expected_type)

        if expected_type in CUSTOM_TYPES and isinstance(value, dict):
            #print("BOOOM",value)
            #return await scheme.normalize(value, CUSTOM_TYPES[expected_type])
            return value
        
        if expected_type not in CUSTOM_TYPES and py_type is None:
            raise DSLRuntimeError(
                f"Unknown type '{expected_type}'",
                meta
            )

        if expected_type in CUSTOM_TYPES or not isinstance(value, py_type):
            raise DSLRuntimeError(
                f"Type error in '{var_name}': expected {expected_type}, "
                f"got {type(value).__name__}",
                meta
            )

        return value


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