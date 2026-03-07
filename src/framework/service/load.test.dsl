imports: {
    'load':resource("framework/service/load.py") |> get("outputs");
};

exports: {
    //"bootstrap": imports.load.bootstrap;
    //"generate_checksum": imports.load.generate_checksum;
    "resource": imports.load.resource;
    "register": imports.load.register;
};

aaa:print(exports);

test_suite: ();