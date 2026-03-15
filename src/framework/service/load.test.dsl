imports: {
    'load':resource("framework/service/load.py");
};

aaa:imports.load |> print("############");

exports: {
    "resource": imports.load.resource;
    "register": imports.load.register;
};

test_suite: (
    { 
        "action": exports.resource;
        "inputs": {'path':"framework/service/load.py"};
        "outputs": true;
        "assert":@received.success == @expected;
        "note": "test resource"; 
    },
);