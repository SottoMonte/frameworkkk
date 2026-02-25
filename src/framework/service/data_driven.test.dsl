imports: {
    'flow':resource("framework/service/flow.py");
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
    x:"19";
},(str:x);

scheme:catch_error := imports.flow.outputs.catch((error_function,[10],{}),(print,[1],{})) |> print  ;