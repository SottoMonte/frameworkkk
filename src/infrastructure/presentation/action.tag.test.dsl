imports: {
    'infrastructure':resource("src/infrastructure/presentation/starlette.py");
};

exports: {
    'driver': imports.infrastructure.Adapter;
};

driver : exports.driver(messenger:messenger, defender:defender);

//aaaa:print(imports.infrastructure.presentation.Attribute.CLICK.value);
dict:TAG_ATTRIBUTES := imports.infrastructure.presentation._ATTRIBUTES_SCHEMA.action;

full_attr_input: {
    "id":"test";
    "class":"test";
    "style":"test";
    "data-test":"test";
    "aria-label":"test";
};

/* ============================================================
    11. TEST SUITE
============================================================ */

tuple:test_suite := (
    { 
        "action": driver.mount_tag;
        "inputs": "action", {'type': 'form'; 'act':'GET'; 'route':'/test'};
        "outputs": '<form method="GET" action="/test"></form>';
        "assert":@received.outputs == @expected;
        "note": "Render width full";
    },
)