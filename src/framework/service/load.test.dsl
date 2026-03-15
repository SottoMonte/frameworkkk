exports: {
    "resource": imports.load.resource;
    "register": imports.load.register;
};

imports: {
    'load':resource("framework/service/load.py");
};

aaa:imports.load |> print("############");

nested: {
    a:{
        c:b;
        b:{x:123}
    };
    b:{x:123};
}

cioa :nested.a.a.c |> print("############");


test_suite: (
    { 
        "action": exports.resource;
        "inputs": {'path':"framework/service/load.py"};
        "outputs": true;
        "assert":@received.success == @expected;
        "note": "test resource"; 
    },
);