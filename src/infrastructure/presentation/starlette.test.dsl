imports: {
    'presentation':resource("src/infrastructure/presentation/starlette.py");
};

exports: {
    'driver': imports.presentation.Adapter;
};

/* ============================================================
    11. TEST SUITE
============================================================ */

tuple:test_suite := (
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text>10</Text>'};
        "outputs": '<Text>10</Text>';
        "assert":@received.outputs == @expected;
        "note": "Render text"; 
    },
);