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
            //"posts",
            //"posts/{id}",
            //"posts/{id}/comments",
            "users",
            "users?{% for key, value in filter.eq.items() %}{{ key }}={{ value }}{% if not loop.last %}&{% endif %}{% endfor %}",
            "users/{{filter.eq.id}}",
            "users/{{filter.eq.id}}/posts",
            "users/{{filter.eq.id}}/albums",
            "users/{{filter.eq.id}}/todos",
            //"albums",
            //"albums/{id}",
            //"albums/{id}/photos",
            //"photos",
            //"photos/{id}",
            //"comments",
            //"comments/{id}",
            //"todos",
            //"todos/{id}",
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
        "assert": @received.outputs.0 == @expected & @received.success == true;
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
    /*{
        "action": exports.serial;
        "inputs":((pass,[1],{}),(pass,[2],{}));
        "outputs": [(1),(3)];
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "serial";
    },
    { 
        "action": exports.parallel; 
        "inputs":((pass,[1],{}),(pass,[2],{})); 
        "outputs": [(1), (2)]; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "parallel"; 
    },
    { 
        "action": exports.pipeline; 
        "inputs":((pass,["ciao"],{}),(pass,[1],{}));
        "outputs": [("ciao"),(1)]; 
        "assert": @received.outputs == @expected & @received.success == true; 
        "note": "pipeline"; 
    },
    { 
        "action": exports.pipeline; 
        "inputs":((error_function,["ciao"],{}),(pass,[1],{}));
        "outputs": None;
        "assert": @received.outputs == @expected & @received.success == false; 
        "note": "pipeline"; 
    },
    { 
        "action": exports.pipeline; 
        "inputs":((pass,[1],{}),(error_function,["ciao"],{}));
        "outputs": None;
        "assert": @received.outputs == @expected & @received.success == false; 
        "note": "pipeline"; 
    },
    { 
        "action": exports.switch;
        "inputs":({
            True:(pass,["ciao"],{});
            @case !=1:(pass,[111],{});
        },{'case':1});
        "outputs": ("ciao");
        "assert": @received.outputs == @expected & @received.success == true; 
        "note": "switch";
    },
    { 
        "action": exports.switch;
        "inputs":({True:(pass,["ciao"],{});@case==1:(pass,[123],{});},{'case':1});
        "outputs": token_print; 
        "assert": @received.outputs == @expected & @received.success == true; 
        "note": "switch"; 
    },
    { 
        "action": exports.foreach; 
        "inputs":([1,2],(pass,[3],{})); 
        "outputs": [(1, 3), (2, 3)]; 
        "assert": @received.outputs == @expected & @received.success == true; 
        "note": "foreach"; 
    },
    { 
        "action": exports.foreach;
        "inputs":((1,2),(pass,(3),{})); 
        "outputs": [(1, 3), (2, 3)]; 
        "assert": @received.outputs == @expected & @received.success == true; 
        "note": "foreach"; 
    },
    { 
        "action": exports.catch; 
        "inputs":((error_function,[10],{}),(pass,[123],{})); 
        "outputs": token_print; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "catch"; 
    },
    { 
        "action": exports.pass;
        "inputs":(10); 
        "outputs": 10; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "Pass flow"; 
    },
    { 
        "action": exports.guard;
        "inputs":(1==1); 
        "outputs": true; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "guard true";
    },
    { 
        "action": exports.guard;
        "inputs":(1 != 1);
        "outputs": false; 
        "assert": @received.outputs == @expected & @received.success == false;
        "note": "guard false";
    },
    { 
        "action": exports.when;
        "inputs":(@numero != 10,(pass,[123],{}),{numero:10});
        "outputs": None;
        "assert": @received.outputs == @expected & @received.success == false;
        "note": "when false";
    },
    { 
        "action": exports.when;
        "inputs":(1 == 1,(pass,[123],{}),{inputs:["test"]}); 
        "outputs": token_print; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "when true";
    },
    { 
        "action": exports.assert;
        "inputs":(10 >= 50);
        "outputs": None;
        "assert": @received.outputs == @expected & @received.success == false;
        "note": "assert false";
    },
    { 
        "action": exports.assert;
        "inputs":(10 <= 50); 
        "outputs": true; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "assert true";
    },
    { 
        "action": exports.assert;
        "inputs":(@numero <= 50, {numero:60});
        "outputs": None;
        "assert": @received.outputs == @expected & @received.success == false;
        "note": "assert false + context"; 
    },
    { 
        "action": exports.assert;
        "inputs":(@numero <= 50, {numero:50});
        "outputs": true; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "assert true + context";
    },
    { 
        "action": exports.pass;
        "inputs":(10); 
        "outputs": 10; 
        "assert": @received.outputs == @expected & @received.success == true;
        "note": "pass";
    },*/
);