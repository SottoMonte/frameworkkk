exports: {
    "resource": imports.load.resource;
    "register": imports.load.register;
};

imports: {
    'load':resource("framework/service/load.py");
};

//aaa:imports.load |> print("############");

/*nested: {
    a:{
        
        
        c:b;
        b:{x:1};
    };
    b:{x:2};
}*/

//cioa :nested.a.c |> print("############");

//aaa:print("############",nested.a.c);


test_suite: (
    { 
        "action": exports.resource;
        "inputs": {'path':"framework/service/load.py"};
        "outputs": true;
        "assert":@received.success == @expected;
        "note": "test resource"; 
    },
);