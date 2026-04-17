any:extension := "py";
imports: {
    'factory':resource("src/framework/service/factory." + extension);
};

exports: {
    'repository': imports.factory.repository;
};

type:schema := {
    "id":          { "type": "integer"; "default": 0; "force_type": "string"; };
    "name":        { "type": "string"; "required": true; "regex": "^[\\w\\-]+$"; };
    "branch":      { "type": "string"; "default": "main"; "regex": "^[\\w\\-]+$"; };
    "description": { "type": "string"; "default": ""; "regex": "^[\\w\\s\\-]+$"; };
    "visibility":  { "type": "boolean"; "default": false; };
    "owner":       { "type": "string"; "default": ""; "regex": "^[\\w\\-]+$"; };
    "location":    { "type": "string"; "default": "0000"; "regex": "^[a-zA-Z0-9_-]+$"; };
    "updated":     { "type": "string"; "regex": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}(:\\d{2})?$"; };
    "created":     { "type": "string"; "regex": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}(:\\d{2})?$"; };
    "stars":       { "type": "integer"; "default": 0; };
    "forks":       { "type": "integer"; "default": 0; };
    "tree":        { "type": "list"; "default": []; };
    "sha":         { "type": "string"; "default": ""; };
};

type:request := {
    "provider":    { 'type': 'string'; 'default': 'unknown'; };
    "location":    { 'type': 'string'; 'default': ''; };
    "operation":   { 'type': 'string'; 'default': 'read'; 'regex': '^(create|read|update|delete|view)$' };
    "repository":  { 'type': 'string'; 'default': ''; };
    "filter":      { 'type': 'dict'; 'default': {}; };
    "payload":     { 'type': 'dict'; 'default': {}; };
};

dict:location := {
    "GITHUB": [
        "repos/{{ owner }}/{{ name }}/git/trees/{{ sha }}?recursive=1",
        "repos/{{ owner }}/{{ name }}/branches/{{ branch }}",
        "repos/{{ owner }}/{{ name }}",
        "repos/{{ filter.eq.owner }}/{{ filter.eq.name }}",
        "orgs/{{ filter.eq.owner }}/repos",
        "orgs/{{ owner }}/repos",
        "users/{{ filter.eq.owner }}/repos",
        "users/{{ owner }}/repos",
        "user/repos?per_page={{ perPage }}&page={{ currentPage }}",
        "user/repos",
    ];
};

dict:values := {
    "tree": { "MODEL": "build_tree_dict" };
};

dict:mapper := {
    "sha":{"GITHUB":"commit.commit.tree.sha"};
    "name":{"GITHUB":"name"};
    "branch":{"GITHUB":"default_branch"};
    "owner":{"GITHUB":"owner.login"};
    "type":{"REPOSITORY":"type"};
    //"content":{"REPOSITORY":"content"};
    "created":{"GITHUB":"created_at"};
    "updated":{"GITHUB":"updated_at"};
    "language":{"REPOSITORY":"language"};
    //"description":{"REPOSITORY":"description"},
    "visibility":{"GITHUB":"private"};
    "tree":{"GITHUB":"tree"};
    "stars":{"GITHUB":"stargazers_count"};
    "forks":{"GITHUB":"forks_count"};
};

actions: {
    "view": {
        "payload": '';
        "logic": '';
    };
};

repository : exports.repository(
    location: location,
    mapper: mapper,
    values: values,
    actions: actions,
    model: schema,
);

request:richiesta := {
    "provider": "GITHUB";
    //"operation": "view";
    "repository": "repository";
    "filter": {
        "eq": {
            "owner": "SottoMonte"
        }
    };
    "payload": {
        "owner": "SottoMonte";
        "name": "framework"
    }
};

/* ============================================================
    TEST SUITE
============================================================ */

tuple:test_suite := (
    // -- GET_REQUIREMENTS EDGE CASES --
    { 
        "action": repository.get_requirements;
        "inputs": {"template_str": ""};
        "outputs": [];
        "assert": @received.outputs == [];
        "note": "AST: Stringa vuota ritorna lista vuota"; 
    },
    { 
        "action": repository.get_requirements;
        "inputs": {"template_str": "repos/{{filter.eq.items()}}"};
        "outputs": None;
        "assert": @received.success == true;
        "note": "AST: Rimozione metodi dict standard (items)"; 
    },
    /*{ 
        "action": repository.get_requirements;
        "inputs": {"template_str": "repos/{{ 1 + }}"}; # Invalid Jinja, triggers except
        "outputs": [];
        "assert": @received.success == true;
        "note": "AST: Jinja Error triggers Fallback Regex"; 
    },*/
    
    // -- SELECT EDGE CASES --
    { 
        "action": repository.select;
        "inputs": {
            "templates": ["user/repos", "repos/{{owner}}/{{name}}"];
            "data": {"owner": "SottoMonte"}
        };
        "outputs": "user/repos";
        "assert": @received.outputs == @expected;
        "note": "AST Selector: Fallback a template statico se requisiti incompleti"; 
    },
    { 
        "action": repository.select;
        "inputs": {
            "templates": ["repos/{{owner}}", "repos/{{owner}}/{% if True %}1{% endif %}"];
            "data": {"owner": "SottoMonte"}
        };
        "outputs": "repos/{{owner}}/{% if True %}1{% endif %}";
        "assert": @received.outputs == @expected;
        "note": "AST Selector: Bonus per tag logici Jinja {%"; 
    },
    { 
        "action": repository.select;
        "inputs": {
            "templates": ["repos/{{owner}}"];
            "data": {}
        };
        "outputs": None;
        "assert": @received.outputs == None;
        "note": "AST Selector: Ritorna None se nessun template è soddisfatto dal payload"; 
    },

    // -- RESULTS EDGE CASES --
    {
        "action": repository.results;
        "inputs": {"transaction": {"result": [{"id": 1}, "invalid", {"id": 2}]}; "profile": "GITHUB"};
        "outputs": {"result": [{"id": 1}, "invalid", {"id": 2}]};
        "assert": @received.outputs == @expected;
        "note": "Pass-through Hook logic handler";
    },

    // -- PARAMETERS EDGE CASES --
    {
        "action": repository.parameters;
        "inputs": {"provider": "GITHUB"; "operation": "view"; "filter": {"eq": {"owner": "SottoMonte"}}};
        "outputs": None;
        "assert": @received.success == true;
        "note": "Orchestratore Parametri Base"; 
    },
    {
        "action": repository.parameters;
        "inputs": {"provider": "GITHUB"; "operation": "view"; "filter": {"eq": {"targetX": "NotFound"}}};
        "outputs": None;
        "assert": @received.success == false;
        "note": "Orchestratore Error: Lancia eccezione (ValueError) se il selector fallisce"; 
    }
);