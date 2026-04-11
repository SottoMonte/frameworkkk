imports: {
    "presentation":resource("src/infrastructure/presentation/starlette.py");
};

exports: {
    "driver": imports.presentation.Adapter;
};

//driver : imports.presentation.Adapter(messenger:messenger, defender:defender);

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

input_attri_1 : {"width": "full"; "height": "full"};
output_attri_1 : {"class": " w-full h-full"};
/* ============================================================
    11. TEST SUITE
============================================================ */

tuple:test_suite := (
    { 
        "action": imports.presentation.attrs;
        "inputs": "container", {attrs: input_attri_1};
        "outputs": output_attri_1;
        "assert":@received.outputs == @expected;
        "note": "Render width full";
    },
    /* ─── WIDTH ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.width; "inputs": "full";    "outputs": "w-full";    "assert": @received.outputs == @expected; "note": "width: keyword full"; },
    { "action": imports.presentation.mapping_attributes.width; "inputs": "1/2";     "outputs": "w-1/2";     "assert": @received.outputs == @expected; "note": "width: keyword 1/2"; },
    { "action": imports.presentation.mapping_attributes.width; "inputs": "1/3";     "outputs": "w-1/3";     "assert": @received.outputs == @expected; "note": "width: keyword 1/3"; },
    { "action": imports.presentation.mapping_attributes.width; "inputs": "1/4";     "outputs": "w-1/4";     "assert": @received.outputs == @expected; "note": "width: keyword 1/4"; },
    { "action": imports.presentation.mapping_attributes.width; "inputs": "auto";    "outputs": "w-auto";    "assert": @received.outputs == @expected; "note": "width: keyword auto"; },
    { "action": imports.presentation.mapping_attributes.width; "inputs": "200px";   "outputs": "w-[200px]"; "assert": @received.outputs == @expected; "note": "width: px arbitrary value"; },
    { "action": imports.presentation.mapping_attributes.width; "inputs": "50%";     "outputs": "w-[50%]";   "assert": @received.outputs == @expected; "note": "width: percent arbitrary value"; },
    { "action": imports.presentation.mapping_attributes.width; "inputs": "unknown"; "outputs": "";          "assert": @received.outputs == @expected; "note": "width: unknown → empty string"; },

    /* ─── HEIGHT ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.height; "inputs": "full";   "outputs": "h-full";    "assert": @received.outputs == @expected; "note": "height: keyword full"; },
    { "action": imports.presentation.mapping_attributes.height; "inputs": "1/2";    "outputs": "h-1/2";     "assert": @received.outputs == @expected; "note": "height: keyword 1/2"; },
    { "action": imports.presentation.mapping_attributes.height; "inputs": "1/3";    "outputs": "h-1/3";     "assert": @received.outputs == @expected; "note": "height: keyword 1/3"; },
    { "action": imports.presentation.mapping_attributes.height; "inputs": "1/4";    "outputs": "h-1/4";     "assert": @received.outputs == @expected; "note": "height: keyword 1/4"; },
    { "action": imports.presentation.mapping_attributes.height; "inputs": "auto";   "outputs": "h-auto";    "assert": @received.outputs == @expected; "note": "height: keyword auto"; },
    { "action": imports.presentation.mapping_attributes.height; "inputs": "100px";  "outputs": "h-[100px]"; "assert": @received.outputs == @expected; "note": "height: px arbitrary value"; },
    { "action": imports.presentation.mapping_attributes.height; "inputs": "75%";    "outputs": "h-[75%]";   "assert": @received.outputs == @expected; "note": "height: percent arbitrary value"; },

    /* ─── MAX-HEIGHT ─────────────────────────────────────────── */
    //{ "action": imports.presentation.mapping_attributes["max-height"]; "inputs": "300px"; "outputs": "max-h-[300px]"; "assert": @received.outputs == @expected; "note": "max-height: px value"; },
    //{ "action": imports.presentation.mapping_attributes["max-height"]; "inputs": "80%";   "outputs": "max-h-[80%]";   "assert": @received.outputs == @expected; "note": "max-height: percent value"; },
    //{ "action": imports.presentation.mapping_attributes["max-height"]; "inputs": "auto";  "outputs": "";              "assert": @received.outputs == @expected; "note": "max-height: non-unit → empty"; },

    /* ─── MIN-HEIGHT ─────────────────────────────────────────── */
    //{ "action": imports.presentation.mapping_attributes["min-height"]; "inputs": "100px"; "outputs": "min-h-[100px]"; "assert": @received.outputs == @expected; "note": "min-height: px value"; },
    //{ "action": imports.presentation.mapping_attributes["min-height"]; "inputs": "20%";   "outputs": "min-h-[20%]";   "assert": @received.outputs == @expected; "note": "min-height: percent value"; },

    /* ─── MAX-WIDTH ──────────────────────────────────────────── */
    //{ "action": imports.presentation.mapping_attributes["max-width"]; "inputs": "640px"; "outputs": "max-w-[640px]"; "assert": @received.outputs == @expected; "note": "max-width: px value"; },
    //{ "action": imports.presentation.mapping_attributes["max-width"]; "inputs": "100%";  "outputs": "max-w-[100%]";  "assert": @received.outputs == @expected; "note": "max-width: percent value"; },

    /* ─── MIN-WIDTH ──────────────────────────────────────────── */
    //{ "action": imports.presentation.mapping_attributes["min-width"]; "inputs": "200px"; "outputs": "min-w-[200px]"; "assert": @received.outputs == @expected; "note": "min-width: px value"; },

    /* ─── PADDING ────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.padding; "inputs": "10px";               "outputs": "p-[10px]";                                          "assert": @received.outputs == @expected; "note": "padding: single value"; },
    { "action": imports.presentation.mapping_attributes.padding; "inputs": "10px,20px";           "outputs": "py-[10px] px-[20px]";                               "assert": @received.outputs == @expected; "note": "padding: 2 values → py/px"; },
    { "action": imports.presentation.mapping_attributes.padding; "inputs": "10px,20px,30px,40px"; "outputs": "pt-[10px] pb-[20px] pl-[30px] pr-[40px]";          "assert": @received.outputs == @expected; "note": "padding: 4 values → pt/pb/pl/pr"; },

    /* ─── MARGIN ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.margin; "inputs": "10px";             "outputs": "m-[10px]";                                       "assert": @received.outputs == @expected; "note": "margin: single value"; },
    { "action": imports.presentation.mapping_attributes.margin; "inputs": "5px,15px";         "outputs": "my-[5px] mx-[15px]";                             "assert": @received.outputs == @expected; "note": "margin: 2 values → my/mx"; },
    { "action": imports.presentation.mapping_attributes.margin; "inputs": "1px,2px,3px,4px";  "outputs": "mt-[1px] mb-[2px] ml-[3px] mr-[4px]";          "assert": @received.outputs == @expected; "note": "margin: 4 values"; },

    /* ─── EXPAND ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.expand; "inputs": "true";  "outputs": "flex-1"; "assert": @received.outputs == @expected; "note": "expand: true → flex-1"; },
    { "action": imports.presentation.mapping_attributes.expand; "inputs": "false"; "outputs": "";       "assert": @received.outputs == @expected; "note": "expand: false → empty"; },

    /* ─── OVERFLOW ───────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.overflow; "inputs": "auto";    "outputs": "overflow-auto";    "assert": @received.outputs == @expected; "note": "overflow: auto"; },
    { "action": imports.presentation.mapping_attributes.overflow; "inputs": "hidden";  "outputs": "overflow-hidden";  "assert": @received.outputs == @expected; "note": "overflow: hidden"; },
    { "action": imports.presentation.mapping_attributes.overflow; "inputs": "visible"; "outputs": "overflow-visible"; "assert": @received.outputs == @expected; "note": "overflow: visible"; },
    { "action": imports.presentation.mapping_attributes.overflow; "inputs": "scroll";  "outputs": "overflow-scroll";  "assert": @received.outputs == @expected; "note": "overflow: scroll"; },
    { "action": imports.presentation.mapping_attributes.overflow; "inputs": "clip";    "outputs": "overflow-clip";    "assert": @received.outputs == @expected; "note": "overflow: clip"; },
    { "action": imports.presentation.mapping_attributes.overflow; "inputs": "none";    "outputs": "overflow-hidden";  "assert": @received.outputs == @expected; "note": "overflow: none maps to hidden"; },
    { "action": imports.presentation.mapping_attributes.overflow; "inputs": "unknown"; "outputs": "";                 "assert": @received.outputs == @expected; "note": "overflow: unknown → empty"; },

    /* ─── COLOR ──────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.color; "inputs": "primary";     "outputs": "text-primary";     "assert": @received.outputs == @expected; "note": "color: semantic primary"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "secondary";   "outputs": "text-secondary";   "assert": @received.outputs == @expected; "note": "color: semantic secondary"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "success";     "outputs": "text-success";     "assert": @received.outputs == @expected; "note": "color: semantic success"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "danger";      "outputs": "text-danger";      "assert": @received.outputs == @expected; "note": "color: semantic danger"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "warning";     "outputs": "text-warning";     "assert": @received.outputs == @expected; "note": "color: semantic warning"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "info";        "outputs": "text-info";        "assert": @received.outputs == @expected; "note": "color: semantic info"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "light";       "outputs": "text-light";       "assert": @received.outputs == @expected; "note": "color: semantic light"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "dark";        "outputs": "text-dark";        "assert": @received.outputs == @expected; "note": "color: semantic dark"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "white";       "outputs": "text-white";       "assert": @received.outputs == @expected; "note": "color: white"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "black";       "outputs": "text-black";       "assert": @received.outputs == @expected; "note": "color: black"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "transparent"; "outputs": "text-transparent"; "assert": @received.outputs == @expected; "note": "color: transparent"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "#ff0000";     "outputs": "text-[#ff0000]";   "assert": @received.outputs == @expected; "note": "color: hex → arbitrary"; },
    { "action": imports.presentation.mapping_attributes.color; "inputs": "unknown";     "outputs": "";                 "assert": @received.outputs == @expected; "note": "color: unknown → empty"; },

    /* ─── COLOR.BORDER ───────────────────────────────────────── */
    //{ "action": imports.presentation.mapping_attributes["color.border"]; "inputs": "#333"; "outputs": "border-[#333]"; "assert": @received.outputs == @expected; "note": "color.border: hex → border"; },
    //{ "action": imports.presentation.mapping_attributes["color.border"]; "inputs": "red";  "outputs": "";              "assert": @received.outputs == @expected; "note": "color.border: non-hex → empty"; },

    /* ─── SPACING (gap) ──────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.spacing; "inputs": "16px";  "outputs": "gap-[16px]"; "assert": @received.outputs == @expected; "note": "spacing: px value"; },
    { "action": imports.presentation.mapping_attributes.spacing; "inputs": "5%";    "outputs": "gap-[5%]";   "assert": @received.outputs == @expected; "note": "spacing: percent value"; },
    { "action": imports.presentation.mapping_attributes.spacing; "inputs": "small"; "outputs": "";           "assert": @received.outputs == @expected; "note": "spacing: non-unit → empty"; },

    /* ─── JUSTIFY ────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.justify; "inputs": "start";   "outputs": "justify-start";   "assert": @received.outputs == @expected; "note": "justify: start"; },
    { "action": imports.presentation.mapping_attributes.justify; "inputs": "end";     "outputs": "justify-end";     "assert": @received.outputs == @expected; "note": "justify: end"; },
    { "action": imports.presentation.mapping_attributes.justify; "inputs": "center";  "outputs": "justify-center";  "assert": @received.outputs == @expected; "note": "justify: center"; },
    { "action": imports.presentation.mapping_attributes.justify; "inputs": "between"; "outputs": "justify-between"; "assert": @received.outputs == @expected; "note": "justify: between"; },
    { "action": imports.presentation.mapping_attributes.justify; "inputs": "around";  "outputs": "justify-around";  "assert": @received.outputs == @expected; "note": "justify: around"; },
    { "action": imports.presentation.mapping_attributes.justify; "inputs": "evenly";  "outputs": "justify-evenly";  "assert": @received.outputs == @expected; "note": "justify: evenly"; },
    { "action": imports.presentation.mapping_attributes.justify; "inputs": "unknown"; "outputs": "";                "assert": @received.outputs == @expected; "note": "justify: unknown → empty"; },

    /* ─── ALIGN ──────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.align; "inputs": "start";   "outputs": "items-start";   "assert": @received.outputs == @expected; "note": "align: start"; },
    { "action": imports.presentation.mapping_attributes.align; "inputs": "end";     "outputs": "items-end";     "assert": @received.outputs == @expected; "note": "align: end"; },
    { "action": imports.presentation.mapping_attributes.align; "inputs": "center";  "outputs": "items-center";  "assert": @received.outputs == @expected; "note": "align: center"; },
    { "action": imports.presentation.mapping_attributes.align; "inputs": "stretch"; "outputs": "items-stretch"; "assert": @received.outputs == @expected; "note": "align: stretch"; },

    /* ─── POSITION ───────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.position; "inputs": "static";   "outputs": "static";   "assert": @received.outputs == @expected; "note": "position: static"; },
    { "action": imports.presentation.mapping_attributes.position; "inputs": "relative";  "outputs": "relative"; "assert": @received.outputs == @expected; "note": "position: relative"; },
    { "action": imports.presentation.mapping_attributes.position; "inputs": "absolute";  "outputs": "absolute"; "assert": @received.outputs == @expected; "note": "position: absolute"; },
    { "action": imports.presentation.mapping_attributes.position; "inputs": "fixed";     "outputs": "fixed";    "assert": @received.outputs == @expected; "note": "position: fixed"; },
    { "action": imports.presentation.mapping_attributes.position; "inputs": "sticky";    "outputs": "sticky";   "assert": @received.outputs == @expected; "note": "position: sticky"; },

    /* ─── RADIUS ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.radius; "inputs": "none";   "outputs": "rounded-none"; "assert": @received.outputs == @expected; "note": "radius: none"; },
    { "action": imports.presentation.mapping_attributes.radius; "inputs": "small";  "outputs": "rounded-sm";   "assert": @received.outputs == @expected; "note": "radius: small"; },
    { "action": imports.presentation.mapping_attributes.radius; "inputs": "medium"; "outputs": "rounded-md";   "assert": @received.outputs == @expected; "note": "radius: medium"; },
    { "action": imports.presentation.mapping_attributes.radius; "inputs": "large";  "outputs": "rounded-lg";   "assert": @received.outputs == @expected; "note": "radius: large"; },
    { "action": imports.presentation.mapping_attributes.radius; "inputs": "full";   "outputs": "rounded-full"; "assert": @received.outputs == @expected; "note": "radius: full"; },

    /* ─── BORDER ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.border; "inputs": "2px";             "outputs": "border-[2px]";                                           "assert": @received.outputs == @expected; "note": "border: single value"; },
    { "action": imports.presentation.mapping_attributes.border; "inputs": "1px,2px";         "outputs": "border-y-[1px] border-x-[2px]";                          "assert": @received.outputs == @expected; "note": "border: 2 values → y/x"; },
    { "action": imports.presentation.mapping_attributes.border; "inputs": "1px,2px,3px,4px"; "outputs": "border-t-[1px] border-b-[2px] border-l-[3px] border-r-[4px]"; "assert": @received.outputs == @expected; "note": "border: 4 values → t/b/l/r"; },

    /* ─── SHADOW ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.shadow; "inputs": "none";   "outputs": "shadow-none"; "assert": @received.outputs == @expected; "note": "shadow: none"; },
    { "action": imports.presentation.mapping_attributes.shadow; "inputs": "min";    "outputs": "shadow-sm";   "assert": @received.outputs == @expected; "note": "shadow: min"; },
    { "action": imports.presentation.mapping_attributes.shadow; "inputs": "medium"; "outputs": "shadow-md";   "assert": @received.outputs == @expected; "note": "shadow: medium"; },
    { "action": imports.presentation.mapping_attributes.shadow; "inputs": "large";  "outputs": "shadow-lg";   "assert": @received.outputs == @expected; "note": "shadow: large"; },
    { "action": imports.presentation.mapping_attributes.shadow; "inputs": "max";    "outputs": "shadow-xl";   "assert": @received.outputs == @expected; "note": "shadow: max"; },

    /* ─── BACKGROUND ─────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.background; "inputs": "unknown";      "outputs": "";                               "assert": @received.outputs == @expected; "note": "background: unknown → empty"; },
    { "action": imports.presentation.mapping_attributes.background; "inputs": "none";         "outputs": "bg-transparent";                 "assert": @received.outputs == @expected; "note": "background: none → transparent"; },
    { "action": imports.presentation.mapping_attributes.background; "inputs": "#fff";       "outputs": "bg-[#fff]";                      "assert": @received.outputs == @expected; "note": "background: single color"; },
    { "action": imports.presentation.mapping_attributes.background; "inputs": "#000,#fff";  "outputs": "bg-gradient-to-r from-[#000] to-[#fff]"; "assert": @received.outputs == @expected; "note": "background: gradient (2 colors)"; },

    /* ─── MATTER ─────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.matter; "inputs": "glass";        "outputs": "backdrop-blur-md"; "assert": @received.outputs == @expected; "note": "matter: glass"; },
    { "action": imports.presentation.mapping_attributes.matter; "inputs": "glass-min";    "outputs": "backdrop-blur-sm"; "assert": @received.outputs == @expected; "note": "matter: glass-min"; },
    { "action": imports.presentation.mapping_attributes.matter; "inputs": "glass-medium"; "outputs": "backdrop-blur-lg"; "assert": @received.outputs == @expected; "note": "matter: glass-medium"; },
    { "action": imports.presentation.mapping_attributes.matter; "inputs": "glass-max";    "outputs": "backdrop-blur-xl"; "assert": @received.outputs == @expected; "note": "matter: glass-max"; },

    /* ─── POINTER ────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "auto";        "outputs": "cursor-auto";        "assert": @received.outputs == @expected; "note": "pointer: auto"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "default";     "outputs": "cursor-default";     "assert": @received.outputs == @expected; "note": "pointer: default"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "pointer";     "outputs": "cursor-pointer";     "assert": @received.outputs == @expected; "note": "pointer: pointer"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "wait";        "outputs": "cursor-wait";        "assert": @received.outputs == @expected; "note": "pointer: wait"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "text";        "outputs": "cursor-text";        "assert": @received.outputs == @expected; "note": "pointer: text"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "move";        "outputs": "cursor-move";        "assert": @received.outputs == @expected; "note": "pointer: move"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "not-allowed"; "outputs": "cursor-not-allowed"; "assert": @received.outputs == @expected; "note": "pointer: not-allowed"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "help";        "outputs": "cursor-help";        "assert": @received.outputs == @expected; "note": "pointer: help"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "crosshair";   "outputs": "cursor-crosshair";   "assert": @received.outputs == @expected; "note": "pointer: crosshair"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "zoom-in";     "outputs": "cursor-zoom-in";     "assert": @received.outputs == @expected; "note": "pointer: zoom-in"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "zoom-out";    "outputs": "cursor-zoom-out";    "assert": @received.outputs == @expected; "note": "pointer: zoom-out"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "grab";        "outputs": "cursor-grab";        "assert": @received.outputs == @expected; "note": "pointer: grab"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "grabbing";    "outputs": "cursor-grabbing";    "assert": @received.outputs == @expected; "note": "pointer: grabbing"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "col-resize";  "outputs": "cursor-col-resize";  "assert": @received.outputs == @expected; "note": "pointer: col-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "row-resize";  "outputs": "cursor-row-resize";  "assert": @received.outputs == @expected; "note": "pointer: row-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "n-resize";    "outputs": "cursor-n-resize";    "assert": @received.outputs == @expected; "note": "pointer: n-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "s-resize";    "outputs": "cursor-s-resize";    "assert": @received.outputs == @expected; "note": "pointer: s-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "e-resize";    "outputs": "cursor-e-resize";    "assert": @received.outputs == @expected; "note": "pointer: e-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "w-resize";    "outputs": "cursor-w-resize";    "assert": @received.outputs == @expected; "note": "pointer: w-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "ne-resize";   "outputs": "cursor-ne-resize";   "assert": @received.outputs == @expected; "note": "pointer: ne-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "nw-resize";   "outputs": "cursor-nw-resize";   "assert": @received.outputs == @expected; "note": "pointer: nw-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "se-resize";   "outputs": "cursor-se-resize";   "assert": @received.outputs == @expected; "note": "pointer: se-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "sw-resize";   "outputs": "cursor-sw-resize";   "assert": @received.outputs == @expected; "note": "pointer: sw-resize"; },
    { "action": imports.presentation.mapping_attributes.pointer; "inputs": "unknown";     "outputs": "";                   "assert": @received.outputs == @expected; "note": "pointer: unknown → empty"; },

    /* ─── TOP / BOTTOM / LEFT / RIGHT ───────────────────────── */
    { "action": imports.presentation.mapping_attributes.top;    "inputs": "10px"; "outputs": "top-[10px]";    "assert": @received.outputs == @expected; "note": "top: px value"; },
    { "action": imports.presentation.mapping_attributes.top;    "inputs": "50%";  "outputs": "top-[50%]";     "assert": @received.outputs == @expected; "note": "top: percent value"; },
    { "action": imports.presentation.mapping_attributes.top;    "inputs": "auto"; "outputs": "";              "assert": @received.outputs == @expected; "note": "top: non-unit → empty"; },
    { "action": imports.presentation.mapping_attributes.bottom; "inputs": "0px";  "outputs": "bottom-[0px]";  "assert": @received.outputs == @expected; "note": "bottom: px value"; },
    { "action": imports.presentation.mapping_attributes.bottom; "inputs": "25%";  "outputs": "bottom-[25%]";  "assert": @received.outputs == @expected; "note": "bottom: percent value"; },
    { "action": imports.presentation.mapping_attributes.left;   "inputs": "100px";"outputs": "left-[100px]";  "assert": @received.outputs == @expected; "note": "left: px value"; },
    { "action": imports.presentation.mapping_attributes.left;   "inputs": "10%";  "outputs": "left-[10%]";    "assert": @received.outputs == @expected; "note": "left: percent value"; },
    { "action": imports.presentation.mapping_attributes.right;  "inputs": "20%";  "outputs": "right-[20%]";   "assert": @received.outputs == @expected; "note": "right: percent value"; },
    { "action": imports.presentation.mapping_attributes.right;  "inputs": "8px";  "outputs": "right-[8px]";   "assert": @received.outputs == @expected; "note": "right: px value"; },

    /* ─── SIZE (font-size) ───────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.size; "inputs": "min";     "outputs": "text-xs";       "assert": @received.outputs == @expected; "note": "size: min → text-xs"; },
    { "action": imports.presentation.mapping_attributes.size; "inputs": "small";   "outputs": "text-sm";       "assert": @received.outputs == @expected; "note": "size: small → text-sm"; },
    { "action": imports.presentation.mapping_attributes.size; "inputs": "medium";  "outputs": "text-base";     "assert": @received.outputs == @expected; "note": "size: medium → text-base"; },
    { "action": imports.presentation.mapping_attributes.size; "inputs": "large";   "outputs": "text-lg";       "assert": @received.outputs == @expected; "note": "size: large → text-lg"; },
    { "action": imports.presentation.mapping_attributes.size; "inputs": "max";     "outputs": "text-xl";       "assert": @received.outputs == @expected; "note": "size: max → text-xl"; },
    { "action": imports.presentation.mapping_attributes.size; "inputs": "14px";    "outputs": "text-[14px]";   "assert": @received.outputs == @expected; "note": "size: px arbitrary"; },
    { "action": imports.presentation.mapping_attributes.size; "inputs": "1.2em";   "outputs": "text-[1.2em]";  "assert": @received.outputs == @expected; "note": "size: em arbitrary"; },
    { "action": imports.presentation.mapping_attributes.size; "inputs": "unknown"; "outputs": "";              "assert": @received.outputs == @expected; "note": "size: unknown → empty"; },

    /* ─── UPPERCASE / LOWERCASE / TRUNCATE ──────────────────── */
    { "action": imports.presentation.mapping_attributes.uppercase; "inputs": "true";  "outputs": "uppercase"; "assert": @received.outputs == @expected; "note": "uppercase: true"; },
    { "action": imports.presentation.mapping_attributes.uppercase; "inputs": "false"; "outputs": "";          "assert": @received.outputs == @expected; "note": "uppercase: false → empty"; },
    { "action": imports.presentation.mapping_attributes.lowercase; "inputs": "true";  "outputs": "lowercase"; "assert": @received.outputs == @expected; "note": "lowercase: true"; },
    { "action": imports.presentation.mapping_attributes.lowercase; "inputs": "false"; "outputs": "";          "assert": @received.outputs == @expected; "note": "lowercase: false → empty"; },
    { "action": imports.presentation.mapping_attributes.truncate;  "inputs": "true";  "outputs": "truncate";  "assert": @received.outputs == @expected; "note": "truncate: true"; },
    { "action": imports.presentation.mapping_attributes.truncate;  "inputs": "false"; "outputs": "";          "assert": @received.outputs == @expected; "note": "truncate: false → empty"; },

    /* ─── FONT ───────────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.font; "inputs": "bold"; "outputs": "font-bold"; "assert": @received.outputs == @expected; "note": "font: bold"; },
    { "action": imports.presentation.mapping_attributes.font; "inputs": "sans"; "outputs": "font-sans"; "assert": @received.outputs == @expected; "note": "font: sans"; },
    { "action": imports.presentation.mapping_attributes.font; "inputs": "mono"; "outputs": "font-mono"; "assert": @received.outputs == @expected; "note": "font: mono"; },

    /* ─── SPACING.TEXT (letter-spacing) ─────────────────────── */
    //{ "action": imports.presentation.mapping_attributes["spacing.text"]; "inputs": "min";    "outputs": "tracking-tighter"; "assert": @received.outputs == @expected; "note": "spacing.text: min → tighter"; },
    //{ "action": imports.presentation.mapping_attributes["spacing.text"]; "inputs": "normal"; "outputs": "tracking-normal"; "assert": @received.outputs == @expected; "note": "spacing.text: normal"; },
    //{ "action": imports.presentation.mapping_attributes["spacing.text"]; "inputs": "max";    "outputs": "tracking-wide";   "assert": @received.outputs == @expected; "note": "spacing.text: max → wide"; },
    //{ "action": imports.presentation.mapping_attributes["spacing.text"]; "inputs": "2px";    "outputs": "tracking-[2px]";  "assert": @received.outputs == @expected; "note": "spacing.text: px arbitrary"; },
    //{ "action": imports.presentation.mapping_attributes["spacing.text"]; "inputs": "0.1em";  "outputs": "tracking-[0.1em]";"assert": @received.outputs == @expected; "note": "spacing.text: em arbitrary"; },

    /* ─── HEIGHT.TEXT (line-height) ─────────────────────────── */
    //{ "action": get(imports.presentation.mapping_attributes,"height.text"); "inputs": "1.5";  "outputs": "leading-[1.5]";  "assert": @received.outputs == @expected; "note": "height.text: unitless ratio"; },
    //{ "action": imports.presentation.mapping_attributes["height.text"]; "inputs": "24px"; "outputs": "leading-[24px]"; "assert": @received.outputs == @expected; "note": "height.text: px value"; },

    /* ─── ALIGN.TEXT ─────────────────────────────────────────── */
    //{ "action": imports.presentation.mapping_attributes["align.text"]; "inputs": "left";   "outputs": "text-left";   "assert": @received.outputs == @expected; "note": "align.text: left"; },
    //{ "action": imports.presentation.mapping_attributes["align.text"]; "inputs": "center"; "outputs": "text-center"; "assert": @received.outputs == @expected; "note": "align.text: center"; },
    //{ "action": imports.presentation.mapping_attributes["align.text"]; "inputs": "right";  "outputs": "text-right";  "assert": @received.outputs == @expected; "note": "align.text: right"; },

    /* ─── THICKNESS ──────────────────────────────────────────── */
    { "action": imports.presentation.mapping_attributes.thickness; "inputs": "2px";  "outputs": "border-[2px]"; "assert": @received.outputs == @expected; "note": "thickness: px → arbitrary border"; },
    { "action": imports.presentation.mapping_attributes.thickness; "inputs": "thin"; "outputs": "border-thin";  "assert": @received.outputs == @expected; "note": "thickness: keyword passthrough"; },
)