imports: {
    'load':resource("framework/service/load.py");
};

aaa:imports.load |> print("############");

exports: {
    //"bootstrap": imports.load.bootstrap;
    //"generate_checksum": imports.load.generate_checksum;
    "resource": imports.load.resource;
    "register": imports.load.register;
};

test_suite: (
    { 
        "action": exports.resource;
        "inputs": {'path':"framework/service/load.py"};
        "outputs": 10;
        "assert":@received == @expected;
        "note": "test resource"; 
    },
);