imports: {
    'module':resource("src/framework/manager/storekeeper." + extension);
};

exports: {
    'assert': imports.storekeeper.assertt;
    'foreach': imports.storekeeper.foreach;
};

type:scheme := {
    "action": {
        "type": "string";
        "default": "unknown";
    };
    "inputs": {
        "type": "list";
        "default": [];
    };
    "outputs": {
        "type": "list";
        "default": [];
        "convert": list;
    };
    "errors": {
        "type": "list";
        "default": [];
    };
    "success": {
        "type": "boolean";
        "default": false;
    };
    "time": {
        "type": "string";
        "default": "0";
    };
    "worker": {
        "type": "string";
        "default": "unknown";
    };
};

storekeeper:imports.module.storekeeper(executor:None,persistences:[]);

"sad":print(storekeeper);

function:success_function := (str:y){x:y;}(str:x);

tuple:test_suite := (
    {
        "action": storekeeper.overview;
        "inputs":{session:[];storekeeper:{'operation':'view';'repository':'users'}};
        "outputs": [];
        "assert": @received.outputs == @expected & @received.success == true;
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