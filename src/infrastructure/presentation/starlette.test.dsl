imports: {
    'presentation':resource("src/infrastructure/presentation/starlette.py");
};

exports: {
    'driver': imports.presentation.Adapter;
};

driver : imports.presentation.Adapter(messenger:messenger, defender:defender);

Tags: {
    WINDOW:"window";
    TEXT:"text";
    INPUT:"input";
    ACTION:"action";
    MEDIA:"media";
    CARD:"card";
    NAVIGATION:"navigation";
    GROUP:"group";
    ROW:"row";
    COLUMN:"column";
    STACK:"stack";
    CONTAINER:"container";
    DEFENDER:"defender";
    MESSENGER:"messenger";
    MESSAGE:"message";
    STOREKEEPER:"storekeeper";
    PRESENTER:"presenter";
    VIEW:"view";
    DIVIDER:"divider";
    ICON:"icon";
    ACCORDION:"accordion";
    RESOURCE:"resource"
};

Attributes: {
    ID:"id";
    TYPE:"type";
    SRC:"src";
    ALT:"alt";
    TITLE:"title";
    WIDTH:"width";
    MAXWIDTH:"max-width";
    MINWIDTH:"min-width";
    HEIGHT:"height";
    MAXHEIGHT:"max-height";
    MINHEIGHT:"min-height";
    CONTROLS:"controls";
    AUTOPLAY:"autoplay";
    LOOP:"loop";
    MUTED:"muted";
    CLASS:"class";
    NAME:"name";
    VALUE:"value";
    PLACEHOLDER:"placeholder";
    REQUIRED:"required";
    DISABLED:"disabled";
    READONLY:"readonly";
    MAX:"max";
    MIN:"min";
    SIZE:"size";
    MULTIPLE:"multiple";
    STYLE:"style"
};

Values: {
    
};

CORE: [Attributes.ID,Attributes.TYPE,Attributes.STYLE,Attributes.CLASS];
MEDIA: [Attributes.SRC,Attributes.ALT,Attributes.TITLE,Attributes.WIDTH,Attributes.MAXWIDTH,Attributes.MINWIDTH,Attributes.HEIGHT,Attributes.MAXHEIGHT,Attributes.MINHEIGHT,Attributes.CONTROLS,Attributes.AUTOPLAY,Attributes.LOOP,Attributes.MUTED];
INPUT: [Attributes.NAME,Attributes.VALUE,Attributes.PLACEHOLDER,Attributes.REQUIRED,Attributes.DISABLED,Attributes.READONLY,Attributes.MAX,Attributes.MIN,Attributes.SIZE,Attributes.MULTIPLE];

Build: {
    Tags.WINDOW: CORE;
    Tags.TEXT: CORE;
    Tags.INPUT: [Attributes.ID,Attributes.TYPE,Attributes.STYLE,Attributes.CLASS,Attributes.NAME,Attributes.VALUE,Attributes.PLACEHOLDER,Attributes.REQUIRED,Attributes.DISABLED,Attributes.READONLY,Attributes.MAX,Attributes.MIN,Attributes.SIZE,Attributes.MULTIPLE];
    Tags.ACTION: CORE;
    Tags.MEDIA: [Attributes.ID,Attributes.TYPE,Attributes.STYLE,Attributes.CLASS,Attributes.SRC,Attributes.ALT,Attributes.TITLE,Attributes.WIDTH,Attributes.MAXWIDTH,Attributes.MINWIDTH,Attributes.HEIGHT,Attributes.MAXHEIGHT,Attributes.MINHEIGHT,Attributes.CONTROLS,Attributes.AUTOPLAY,Attributes.LOOP,Attributes.MUTED];
    Tags.CARD: CORE;
    Tags.NAVIGATION: CORE;
    Tags.GROUP: CORE;
    Tags.ROW: CORE;
    Tags.COLUMN: CORE;
    Tags.STACK: CORE;
    Tags.CONTAINER: CORE;
    Tags.DEFENDER: CORE;
    Tags.MESSENGER: CORE;
    Tags.MESSAGE: CORE;
    Tags.STOREKEEPER: CORE;
    Tags.PRESENTER: CORE;
    Tags.VIEW: CORE;
    Tags.DIVIDER: CORE;
    Tags.ICON: CORE;
    Tags.ACCORDION: CORE;
    Tags.RESOURCE: CORE;
};

scala: ["min","medium","large","max","none"];

/* ============================================================
    11. TEST SUITE
============================================================ */

tuple:test_suite := (
    { 
        "action": imports.presentation.mapping_attributes.width;
        "inputs": 'full';
        "outputs": "w-full";
        "assert":@received.outputs == @expected;
        "note": "Render width full"; 
    },
    /*{ 
        "action": driver.render_template;
        "inputs": {'text':'<Text>10</Text>'};
        "outputs": '<span>10</span>';
        "assert":@received.outputs == @expected;
        "note": "Render text"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="h1">10</Text>'};
        "outputs": '<h1>10</h1>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type h1"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="h2">10</Text>'};
        "outputs": '<h2>10</h2>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type h2"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="h3">10</Text>'};
        "outputs": '<h3>10</h3>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type h3"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="h4">10</Text>'};
        "outputs": '<h4>10</h4>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type h4"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="h5">10</Text>'};
        "outputs": '<h5>10</h5>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type h5"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="h6">10</Text>'};
        "outputs": '<h6>10</h6>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type h6"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="p">10</Text>'};
        "outputs": '<p>10</p>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type p"; 
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="span">10</Text>'};
        "outputs": '<span>10</span>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type span";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="code">10</Text>'};
        "outputs": '<code>10</code>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type code";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Text type="pre">10</Text>'};
        "outputs": '<pre>10</pre>';
        "assert":@received.outputs == @expected;
        "note": "Render text with type pre";
    },
    // -------------------------- Layout --------------------------
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Row></Row>'};
        "outputs": '<div class="row"></div>';
        "assert":@received.outputs == @expected;
        "note": "Render row";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Column></Column>'};
        "outputs": '<div class="col"></div>';
        "assert":@received.outputs == @expected;
        "note": "Render column";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Stack></Stack>'};
        "outputs": '<div class="stack"></div>';
        "assert":@received.outputs == @expected;
        "note": "Render stack";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Divider/>'};
        "outputs": '<hr>';
        "assert":@received.outputs == @expected;
        "note": "Render divider";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Divider type="vertical"/>'};
        "outputs": '<div class="vr"></div>';
        "assert":@received.outputs == @expected;
        "note": "Render divider with type vertical";
    },
    // -------------------------- Input --------------------------
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input/>'};
        "outputs": '<input type="text" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="password"/>'};
        "outputs": '<input type="password" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type password";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="email"/>'};
        "outputs": '<input type="email" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type email";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="number"/>'};
        "outputs": '<input type="number" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type number";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="search"/>'};
        "outputs": '<input type="search" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type search";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="url"/>'};
        "outputs": '<input type="url" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type url";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="tel"/>'};
        "outputs": '<input type="tel" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type tel";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="date"/>'};
        "outputs": '<input type="date" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type date";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="time"/>'};
        "outputs": '<input type="time" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type time";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="week"/>'};
        "outputs": '<input type="week" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type week";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="month"/>'};
        "outputs": '<input type="month" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type month";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="color"/>'};
        "outputs": '<input type="color" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type color";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="file"/>'};
        "outputs": '<input type="file" class="form-control">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type file";
    },
    { 
        "action": driver.render_template;
        "inputs": {'text':'<Input type="hidden"/>'};
        "outputs": '<input type="hidden">';
        "assert":@received.outputs == @expected;
        "note": "Render input with type hidden";
    },*/
)