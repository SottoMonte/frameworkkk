imports: {
    'flow':resource("framework/service/flow.py") |> get("outputs");
};

exports: {
    'assert': imports.flow.assertt;
    'foreach': imports.flow.foreach;
    'pass': imports.flow.passs;
    'catch':  imports.flow.catch;
    'serial': imports.flow.serial;
    'parallel': imports.flow.parallel;
    'retry': imports.flow.retry;
    'pipeline': imports.flow.pipeline;
    'sentry': imports.flow.sentry;
    'switch': imports.flow.switch;
    'when': imports.flow.when;
    'timeout': imports.flow.timeout;
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

function:error_function := (str:y),{
    x:y/2;
},(str:x);

tuple:test_suite := (
    { "target": "exports.catch"; "inputs":((error_function,[10],{}),(print,[123],{})); "filter":"outputs"; "output": 123; "description": "Pass flow"; },
    { "target": "exports.pass"; "inputs":(10); "filter":"outputs"; "output": 10;  },
    { "target": "exports.sentry"; "inputs":("1 == 1"); "filter":"success"; "output": true; "description": "Pass flow"; },
    { "target": "exports.sentry"; "inputs":("1 != 1"); "filter":"success"; "output": false; "description": "Pass flow"; },
    { "target": "exports.when"; "inputs":("1 != 1",(print,[123],{}),{inputs:["test"]}); "filter":"success"; "output": false; "description": "Pass flow"; },
    { "target": "exports.when"; "inputs":("1 == 1",(print,[123],{}),{inputs:["test"]}); "filter":"outputs"; "output": 123; "description": "Pass flow"; },
    { "target": "exports.assert"; "inputs":("10 >= 50"); "filter":"success"; "output": false;  },
    { "target": "exports.assert"; "inputs":("10 <= 50"); "filter":"success"; "output": true;  },
    { "target": "exports.pass"; "inputs":(10); "filter":"outputs"; "output": 10;  },
);