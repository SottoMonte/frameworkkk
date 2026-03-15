any:extension := "py";
imports: {
    'factory':resource("framework/service/factory." + extension);
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
        "payload": view_payload_func;
        "logic": view_logic_func;
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
    /*"filter": {
        "eq": {
            "owner": "SottoMonte"
        }
    };*/
    "payload": {
        "owner": "SottoMonte";
        "name": "framework"
    }
};

/* ============================================================
    TEST SUITE
============================================================ */

tuple:test_suite := (
    { 
        "action": repository.can_format;
        "inputs": {"template": "repos/{{owner}}/{{name}}"; "data": {"owner": "SottoMonte"; "name": "framework"}};
        "outputs": (true, 2);
        "assert": @received.outputs == @expected;
        "note": "Verifica se il template con 2 placeholder è risolvibile"; 
    },
    { 
        "action": repository.do_format;
        "inputs": {"template": "repos/{owner}"; "data": {"owner": "SottoMonte"}};
        "outputs": "repos/SottoMonte";
        "assert": @received.outputs == @expected;
        "note": "Sostituzione corretta del placeholder"; 
    },
    { 
        "action": repository.find_best_template;
        "inputs": {
            "templates": ["user/repos", "repos/{{owner}}/{{name}}"];
            "data": {"owner": "SottoMonte"; "name": "framework"}
        };
        "outputs": "repos/{{owner}}/{{name}}";
        "assert": @received.outputs == @expected;
        "note": "Selezione del template più specifico in base ai dati disponibili"; 
    },
    {
        "action": repository.results;
        "inputs": {"transaction": {"result": [{"id": 1}, "invalid", {"id": 2}]}};
        "outputs": {"result": [{"id": 1}, {"id": 2}]};
        "assert": @received.outputs.result == @expected.result;
        "note": "Normalizzazione transazione: filtro di elementi non dizionari";
    },
    {
        "action": repository.parameters;
        "inputs": richiesta;
        "outputs": richiesta |> union({'location':"repos/SottoMonte/framework"});
        "assert": @received.outputs == @expected;
        "note": "Orchestratore: generazione path finale e provider corretto"; 
    }
);

/*{
    validate: repository.validate_schema;
    build->validate: repository.build_template;
    fetch->build: repository.fetch_data;
    map->fetch|build,validate:   repository.map_values;
    action->map: repository.run_action;
};*/