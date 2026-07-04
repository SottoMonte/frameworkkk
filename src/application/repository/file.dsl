/* Definizione del Modello Repository (Dichiarativo) */
factory:repository := {
    location: {
        "SOURCE": [
            "/tmp/{{filter.eq.filename}}",
            "/tmp",
        ]
    };
    
    model: storekeeper;
    
    values: {
        //"tree": { "MODEL": build_tree_dict };
    };
    
    payloads: {
        //"view": view;
    };
    
    functions: {
        //"update": update_payload;
    };
};