imports: {
    'module':resource("src/framework/manager/storekeeper." + extension);
};

exports: {
    'assert': imports.storekeeper.assertt;
    'foreach': imports.storekeeper.foreach;
};

type:API_user := {
    "id": {
        "type": "integer";
        "required": true;
    };
    "name": {
        "type": "string";
        "required": true;
    };
    "email": {
        "type": "string";
        "required": true;
    };
    "username": {
        "type": "string";
        "required": true;
    };
    "address": {
        "type": "dict";
        "schema": {
            "street": { "type": "string"; "default": "" };
            "suite": { "type": "string"; "default": "" };
            "city": { "type": "string"; "default": "" };
            "zipcode": { "type": "string"; "default": "" };
            "geo": { "type": "dict"; "default": {} };
        };
        "default": {};
    };
    "phone": {
        "type": "string";
        "required": true;
    };
    "website": {
        "type": "string";
        "required": true;
    };
    "company": {
        "type": "dict";
        "schema": {
            "name": { "type": "string"; "default": "" };
            "catchPhrase": { "type": "string"; "default": "" };
            "bs": { "type": "string"; "default": "" };
        };
        "default": {};
    };
};

API:{
    location: {
        "API": [
            "users",
            "users?{% for key, value in filter.eq.items() %}{{ key }}={{ value }}{% if not loop.last %}&{% endif %}{% endfor %}",
            "users/{{filter.eq.id}}",
            "users/{{filter.eq.userId}}/posts?{% for key, value in filter.eq.items() %}{{ key }}={{ value }}{% if not loop.last %}&{% endif %}{% endfor %}",
            "users/{{filter.eq.id}}/albums{% if filter.eq.target_albums %}{% endif %}",
            "users/{{filter.eq.id}}/todos{% if filter.eq.target_todos %}{% endif %}",
            "users?email={{filter['eq']['email']}}",
            "users?username={{filter.eq.user.username}}&website={{filter['eq']['site']}}"
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


storekeeper:imports.module.Storekeeper(executor:executor,persistences:loader.get('persistences'),repositories:{'API':API});
start:storekeeper.start();

function:success_function := (str:y){x:y;}(str:x);

tuple:test_suite := (
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'eq':{'id':1}}}};
        API_user:"outputs" := {
            "id": 1;
            "name": "Leanne Graham";
            "username": "Bret";
            "email": "Sincere@april.biz";
            "address": {"street": "Kulas Light"; "suite": "Apt. 556"; "city": "Gwenborough"; "zipcode": "92998-3874"; "geo": {"lat": "-37.3159"; "lng": "81.1496"}};
            "phone": "1-770-736-8031 x56442";
            "website": "hildegard.org";
            "company": {"name": "Romaguera-Crona"; "catchPhrase": "Multi-layered client-server neural-net"; "bs": "harness real-time e-markets"}
        };
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "overview";
    },
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'eq':{'name':"Ervin Howell"}}}};
        API_user:"outputs" := {
            "id": 2;
            "name": "Ervin Howell";
            "username": "Antonette";
            "email": "Shanna@melissa.tv";
            "address": {
                "street": "Victor Plains";
                "suite": "Suite 879";
                "city": "Wisokyburgh";
                "zipcode": "90566-7771";
                "geo": {"lat": "-43.9509"; "lng": "-34.4618"}
            };
            "phone": "010-692-6593 x09125";
            "website": "anastasia.net";
            "company": {
                "name": "Deckow-Crist";
                "catchPhrase": "Proactive didactic contingency";
                "bs": "synergize scalable supply-chains"
            }
        };
        "assert": @received.outputs.0 == @expected & @received.success == true;
        "note": "overview";
    },
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'eq':{'userId':1;'id':2}}}};
        "outputs" : {
            "userId": 1;
            "id": 2;
            "title": "qui est esse";
            "body": "est rerum tempore vitae\nsequi sint nihil reprehenderit dolor beatae ea dolores neque\nfugiat blanditiis voluptate porro vel nihil molestiae ut reiciendis\nqui aperiam non debitis possimus qui neque nisi nulla";
        };
        "assert": @received.outputs.0.id == 2 & @received.outputs.0.userId == 1 & @received.success == true;
        "note": "overview";
    },
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'neq':{'id':999}}}};
        "outputs" : None;
        "assert": @received.outputs.0.id == 1 & @received.outputs.9.id == 10 & @received.success == true;
        "note": "AST Fallback - Nessun match di pattern = fallback base 'users'";
    },
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'eq':{'email':"Sincere@april.biz"}}}};
        "outputs" : None;
        "assert": @received.outputs.0.id == 1 & @received.success == true;
        "note": "AST Getitem test - Risolve le stringhe bracket notations come ['eq']['email']";
    },
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'eq':{'user':{'username':"Bret"};'site':"hildegard.org"}}}};
        "outputs" : None;
        "assert": @received.outputs.0.id == 1 & @received.success == true;
        "note": "AST Deep Traversal - Gestione mista Bracket e Chain Properties in URL complessi";
    },
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'eq':{'id':1;'target_albums':true}}}};
        "outputs" : None;
        "assert": @received.outputs.0.userId == 1 & @received.success == true;
        "note": "Guarded Template - Recupera gli album dello user risolvendo l'if statement nell'AST";
    },
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'API';'filter':{'eq':{'id':1;'target_todos':true}}}};
        "outputs" : None;
        "assert": @received.outputs.0.userId == 1 & @received.outputs.0.completed == false & @received.success == true;
        "note": "Guarded Template - Recupera le task dello user risolvendo l'if statement nell'AST";
    },
);