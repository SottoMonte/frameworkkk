/* Definizione del Modello Repository (Dichiarativo) */
factory:repository := {
    location: {
        "LOG": [
            "/tmp/{{filter.eq.filename}}",
            "/tmp",
        ]
    };
    
    model: storekeeper;
    
    values: {
        //"tree": { "MODEL": build_tree_dict };
    };
    
    /*mapper: {
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
    };*/
    
    payloads: {
        //"view": view;
    };
    
    functions: {
        //"update": update_payload;
    };
};