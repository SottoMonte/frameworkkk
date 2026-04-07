# OmniPort Agent Framework Skill

This skill provides instructions on how to use the OmniPort Hexagonal Framework. As an agent, you are tasked with building or modifying applications within this ecosystem while strictly adhering to the architectural boundaries.

## 🏗️ Architectural Principles

OmniPort follows a **Hexagonal Architecture** (Ports & Adapters) where the business logic is isolated from the infrastructure.

1.  **Core (src/application)**: This is where everything happens. It contains pure domain logic, UI definitions, and data models.
2.  **Infrastructure (src/infrastructure)**: Contains implementation details (e.g., Starlette for web, Redis for storage). **NEVER MODIFY THIS.**
3.  **Framework (src/framework)**: The engine that orchestrates ports. **NEVER MODIFY THIS.**

## 🛑 Strict Scope Rules

When working with this framework, you are **ONLY** allowed to:
1.  Modify or create files inside `src/application/` and its subdirectories.
2.  Modify `pyproject.toml` to configure project settings or switch adapters.
3.  **DO NOT** touch any other files or directories.

## 📁 Directory Structure (src/application)

- `action/`: Logic flows and tasks defined in `.dsl` or `.py`.
- `model/`: Entity definitions and schemas in `.json`.
- `repository/`: Strategic data access patterns.
- `view/`: User interface definitions using `.xml`.
    - `page/`: Main application pages.
    - `layout/`: Shared layout templates.
    - `components/`: Reusable UI components.
- `policy/`: Security and business rules (e.g., `.rego` or `.dsl`).

## ✍️ DSL (Domain Specific Language)

The framework uses a custom DSL for reactive tasks and logic. 
**IMPORTANT:** Whenever you are tasked to create or modify business logic in a `.dsl` file, you **MUST** first read [src/application/dsl.md](file:///home/asd/framework/src/application/dsl.md) to understand the complete syntax and available built-in functions.

### DSL Features:
- **Assignment**: `var_name := value;`
- **Pipes**: `input |> function1(args) |> function2;`
- **Tasks**: `trigger(kwargs) -> action_or_pipe;`
- **Schemas**: 
  ```dsl
  type:user_schema := {
      "name": { "type": "string", "required": true };
      "age":  { "type": "integer", "default": 18 };
  };
  ```

tick(schedule: 5) -> print("System Heartbeat");
```

### ⚠️ DSL Syntax Constraints
The DSL parser is extremely strict:
- **No Trailing Commas**: Never include a trailing comma in dictionaries `{}` or lists/tuples `()`, `[]`.
- **Comments**: Use `//` for single-line comments. Block comments `/* ... */` are supported but **cannot be nested** and any `*/` inside will close the comment immediately.

## 🖼️ XML Presentation System

UI is defined in XML files which are rendered into HTML/Tailwind by the presentation adapter. 

### ⚠️ XML Syntax Rules
All XML files **MUST** follow strict validation rules. Special characters in text or attributes must be escaped:
- `&` → `&amp;`
- `<` → `&lt;`
- `>` → `&gt;`

For a complete list of tags and attributes, always refer to [src/application/view.md](file:///home/asd/framework/src/application/view.md).

### Important Tags:
- `<Window>`: Main page wrapper.
- `<Navigation>`: Layout headers/nav bars.
- `<Row>`, `<Column>`: Flexbox layouts.
- `<Text>`: H1-H6, p, span (controlled by `type` attribute).
- `<Action>`: Buttons, links, forms.
- `<Container>`: Generic box for layout.
- `<Divider>`: Visual separators.
- `<Icon>`: Icons (e.g., `bi-terminal`).
- `<SVG>`: Native SVG elements are supported.
- **Custom Components**: Any XML file in `view/components/` can be used as a custom tag (e.g. `<MyCard />`). Use `{{ inner | safe }}` to inject children inside your component.

### Common Attributes (mapped to Tailwind):
- `width`, `height`: pixel or percentage (e.g., `width="full"`, `height="100px"`).
- `padding`, `margin`: comma-separated values (e.g., `padding="10px,20px"`).
- `justify`, `align`: `start`, `center`, `end`, `between`, `around`.
- `background`: Hex colors or gradients (e.g., `background="#2ff801,#568dff"`).
- `matter`: Design effects (e.g., `glass`, `glass-max`).
- `font`: `bold`, `mono`, `black`, `extrabold`.

### Example UI:
```xml
<Column padding="20px" background="#f0f0f0">
    <Text type="h1" font="bold" color="#333">Welcome</Text>
    <Row justify="between" align="center">
        <Text type="p">Status: Online</Text>
        <Action type="button" background="#568dff">
            <Text font="bold">REFRESH</Text>
        </Action>
    </Row>
</Column>
```

### ⚡ Server-Driven Reactivity (WebSockets)
You can make any XML element strictly reactive to DSL state changes without writing JS. Use the `bind` attribute to connect it to a node in the DAG.
- **Syntax**: `bind="dsl_alias:node_path"` (e.g. `bind="counter:counter_logic.count"`).
- **Mandatory**: Every element using `bind=` **MUST** explicitly define an `id="..."` attribute, or the framework will explicitly crash to prevent DAG memory leaks.

```xml
<Text id="live_counter" bind="counter:counter_logic.count">
    Value: {{ counter_logic.count }}
</Text>
```

## ⚙️ pyproject.toml Configuration

Use this file to orchestrate the system.

```toml
[project]
name = "my_app"
key = "SECRET_KEY"

[project.policy]
presentation = "web.toml" # Links to src/application/policy/presentation/web.toml

[presentation.backend]
adapter = "starlette"     # Switches the presentation engine
port = "5000"

## 🌐 Routing and Security
All routes and access rules are defined in `src/application/policy/presentation/web.toml`.
1.  **Add a route**: Define a `[[store.data.routes]]` entry. **IMPORTANT**: The `view` path is relative to `src/application/view/page/`. Do **NOT** include the `page/` prefix (e.g., use `view = "portfolio.xml"` and NOT `view = "page/portfolio.xml"`).
2.  **Set a policy**: Create a `[[policies]]` entry to allow/deny access based on `input.path` or `input.principal`.
```

## 🚀 Workflow for Agents

1.  **Define the Model**: Create a JSON schema in `src/application/model/`.
2.  **Implement Logic**: Write the domain behavior in `src/application/action/` using `.dsl`.
3.  **Build the View**: Create the UI in `src/application/view/` using `.xml`. **IMPORTANT**: Refer to [src/application/view.md](file:///home/asd/framework/src/application/view.md) for the full list of tags and attributes.
4.  **Connect in pyproject.toml**: Ensure the project is configured correctly.

## 🛠️ Useful Commands
Always ensure the virtual environment is active before running commands.

- **Activate Venv**: `source venv/bin/activate`
- **Run Server**: `python3 public/main.py`
- **Validate Contracts (DSL)**: `python3 public/main.py --test`
- **Install Dependencies**: `pip install -r requirements.txt`
