/*
    Funzionalità mantenute al 100%:
    ✅ Parsing completo
    ✅ Type validation
    ✅ Function calls (DSL e Python)
    ✅ Pipe expressions
    ✅ Triggers (cron ed event)
    ✅ Include directive
    ✅ Custom types
    ✅ Dotted paths
    ✅ Operations
    ============================================================
    1. TIPI BASE
    ============================================================
*/
integer:const_int := 10;
rational:const_float := 20.5;
str:const_str := "Ciao";
str:const_str_alt := 'Mondo';

boolean:bool_true := True;
boolean:bool_false := False;
boolean:bool_true_alt := true;
boolean:bool_false_alt := false;

function:increment := (int:x){ r: x + 1; }(int:r);
function:fn_double := (int:n){ out: n * 2; }(int:out);
function:fn_sum := (int:x, int:y){ sum: x + y; }(int:sum);
function:fn_increment_pair := (int:val){ inc1: val + 1; inc2: val + 2; }(int:inc1, int:inc2);

any:any_str := "Ciao";
any:any_int := 10;
any:any_bool := True;
any:any_list := [1, 2, 3];
any:any_dict := { "a": 1; "b": 2; };
any:any_tuple := (1, 2, 3);
any:any_fn := increment;

list:collection_mixed_list := [1, 2, "tre", True];
list:collection_list_trailing := [1, 2];
list:collection_list_void := [];

tuple:collection_inline_tuple := 1, 2, 3;
tuple:mixed_inline_tuple := 1, "due", True, 4.0;
tuple:collection_pair := (1, "test");
tuple:tuple_void := ();

dict:collection_dict_trailing := { "a": 1; "b": 2; };
dict:collection_simple_dict := { "chiave": "valore"; "num": 42; };
dict:collection_dict_void := {};

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
        "default": "";
    };
    "worker": {
        "type": "string";
        "default": "unknown";
    };
};

scheme:test_custom_type := {
    "action": "testing";
    "worker": "myself";
};

/* ============================================================
    9. OPERATORI
============================================================ */

int:calc_precedence := 2 + 3 * 4;         
int:calc_div_sub := 10 / 2 - 1;          
int:calc_mod := 10 % 3;                  
int:calc_power := 2 ^ 3;

/* ============================================================
    3. LOGICA E COMPARAZIONI
============================================================ */

any:logic_and_or := True & (10 > 5) or False|>print;
boolean:logic_not := not (5 == 5) or (1 != 2);
boolean:logic_comparison_chain := (10 >= 10) & (5 <= 6) & (2 < 3) & (4 > 1);

/* ============================================================
    10. DOT NOTATION / OGGETTI
============================================================ */

dict:service := {
    "config": { "timeout": 30; };
    "action": (int:x){ r: x + 1; }(int:r);
};

int:res_service_timeout := service.config.timeout;  
//int:res_service_action := service.action(9);

/* ============================================================
    10. PIPE
============================================================ */

//int:pipe_chain_double := 10 |> fn_double |> fn_double;                  

//int:pipe_partial_sum := 10 |> fn_sum(5);  

/* ============================================================
    11. TEST SUITE
============================================================ */

tuple:test_suite := (
    { 
        "action": @placeholder;
        "inputs": {'placeholder':10};
        "outputs": 10;
        "assert":@received == @expected;
        "note": "Placeholder"; 
    },
    { 
        "action": @left == @right;
        "inputs": {"left":10; "right":10};
        "outputs": True;
        "assert":@received == @expected;
        "note": "Comparison operator with variables placeholder"; 
    },
    { 
        "action": fn_double; 
        "inputs": [10];
        "outputs": 20;
        "assert":@received == @expected;
        "note": "Double the input"; 
    },
    { 
        "action": fn_sum; 
        "inputs": [10, 20]; 
        "outputs": 30;
        "assert":@received == @expected;
        "note": "Sum of two numbers"; 
    },
    { 
        "action": fn_increment_pair; 
        "inputs": [10]; 
        "outputs": [11, 12];
        "assert":@received == @expected; 
        "note": "Increment pair of numbers"; 
    },
    { 
        "action": pass;
        "inputs": [tuple_void]; 
        "outputs": (());
        "assert":@received == @expected;
        "note": "Pass void tuple";
    },
);