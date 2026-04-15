/*flow:view := (dict:constants){
    branch_data:storekeeper.gather(**constants|{'payload':payload});
    payload: constants|{ 'sha':branch_data.sha; 'branch':'main' };
}(dict:payload);

flow:update_payload := (dict:constants){
    payload: constants|{ 'method':'PATCH' };
}(dict:payload);*/

/* Definizione del Modello Repository (Dichiarativo) */
factory:repository := {
    location: {
        "GITHUB": [
            "repos/{owner}/{name}/git/trees/{sha}?recursive=1",
            "repos/{owner}/{name}/branches/{branch}",
            "repos/{owner}/{name}",
            "repos/{filter.eq.owner}/{filter.eq.name}",
            "orgs/{filter.eq.owner}/repos",
            "orgs/{owner}/repos",
            "users/{filter.eq.owner}/repos",
            "users/{owner}/repos",
            //"user/repos?per_page={perPage}&page={currentPage}",
            "user/repos",
        ]
    };
    
    model: {};
    
    values: {
        //"tree": { "MODEL": build_tree_dict };
    };
    
    mapper: {
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
    
    payloads: {
        //"view": view;
    };
    
    functions: {
        //"update": update_payload;
    };
};