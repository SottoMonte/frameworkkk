# OmniPort DSL (Domain Specific Language) Reference

The OmniPort framework relies on a custom, reactive DSL to define business logic, state machines, and data transformations. This DSL is designed to be highly declarative and perfectly decoupled from the presentation layer.

## 📝 General Rules
- The DSL uses **Strict JSON-like structures**.
- Statements are separated by `;`.
- **NO trailing commas** are allowed in dictionaries `{}`, lists `[]`, or tuples `()`.
- Comments use `//` for single-line or `/* ... */` for block comments (nested blocks are not allowed).

## 🚀 Defining Reactive Tasks (Nodes)
A `.dsl` file represents a Directed Acyclic Graph (DAG) of nodes.
Nodes either define variables or execute tasks based on triggers.

### Defining State (Assign / Default)
```dsl
counter_logic : {
    // Defines a state variable 'count' with a default value of 0.
    // The arrow points to itself to persist the state.
    count(default: 0) -> counter_logic.count;
};
```

### Defining Actions (Triggers)
Use the format `trigger_name(kwargs) -> action;`
```dsl
increment_btn(deps: false) -> messenger.post(
    session: sid,
    domain: "counter:counter_logic.count",
    payload: (counter_logic.count + 1)
);
```

### Kwargs on Triggers (Task Metadata)
You can declare properties inside the trigger's `()`:
- `default: <value>`: Sets the initial state of the node.
- `deps: [<nodes>]` or `false`: Forces an explicit dependency list. Use `false` to prevent the engine from auto-inferring dependencies.
- `cache: false`: Disables caching for this node (forces execution every time).
- `on_end: "path.to.other.node"`: Triggers another node upon completion.

## ⚡ Pipes (Functional Chaining)
The pipe operator `|>` allows for clean functional transformations of data. The output of the previous step becomes the implicitly first argument of the next function.

```dsl
process_user() -> 
    database.get_user(id) 
    |> transform_user_data(strict: true) 
    |> messenger.post(session: sid, event: "user_loaded");
```

## 🏗️ Data Structures
The DSL supports strongly typed collections:

- **Dictionaries**: `{ "key": "value", "count": 10 }`
- **Lists**: `["apple", "banana", "cherry"]`
- **Tuples**: `(10, 20)`
- **Primitives**: `true`, `false`, `none`, strings (single or double quotes), and numbers.

## 🧮 Operations
Standard logical and mathematical operators are fully supported:
- **Math**: `+`, `-`, `*`, `/`, `%`, `^` (power)
- **Logic**: `and` (or `&`), `or` (or `|`), `not` (or `!`)
- **Comparison**: `==`, `!=`, `<`, `>`, `<=`, `>=`

```dsl
calculate() -> (base_price * 1.22) + shipping_cost;
is_valid() -> (age >= 18) and not is_banned;
```

## 📦 Static Assignments (Variables and Types)
Use `:=` for top-level static declarations, such as Data Schemas.

```dsl
type:user_schema := {
    "name": { "type": "str", "required": true };
    "age":  { "type": "int", "default": 18 };
};
```

## 🔌 Built-in Functions
The DSL natively provides several built-in utilities:
- `print(val)`: Prints to the server console.
- `random(min, max)`: Returns a random integer.
- `keys(dict)`, `values(dict)`: Dictionary extractors.
- `union(dict1, dict2)`: Merges two dictionaries.
- `format("Hello {0}", name)`: String formatting.
- `get(dict, "key.sub")`, `put(dict, "key", "val")`: Deep dictionary traversals.
- `foreach(iterable, function)`: Iterates over a list.

## 🌐 Context Variables (`@`)
If you need to explicitly reference a specific runtime context variable instead of relying on standard resolution, you can prefix it with `@`.
```dsl
fetch() -> database.load(@current_user_id);
```
