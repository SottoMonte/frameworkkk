data: {
    "nome": "Progetto A";
    "versioni": (
        {"id": 1; "status": "completo";},
        {"id": 2; "status": "in_corso"; "dettagli": {"tester": "Mario";};},
        {"id": 3; "status": "fallito";}
    );
    "config": {
        "timeout": 30;
        "log_livello": "DEBUG";
    };
};

dict:utente_schema := {
  "nome": {
    "type": "string";
    "required": False;
  };
  "cognome": {
    "type": "string";
    "required": True;
  };
  "eta": {
    "type": "number";
    "required": True;
  };
  "email": {
    "type": "string";
    "required": False;
    "nullable": True;
  };
  "numero": {
    "type": "number";
    "required": True;
    "min": 0;
  };
  "indirizzo": {
    "type": "string";
    "required": False;
    "nullable": True;
  };
};

dict:user_schema := {
  "name": {
    "type": "string";
    "required": False;
  };
  "surname": {
    "type": "string";
    "required": True;
  };
  "age": {
    "type": "number";
    "required": True;
  };
  "email": {
    "type": "string";
    "required": False;
    "nullable": True;
  };
  "phone": {
    "type": "number";
    "required": True;
    "min": 0;
  };
  "address": {
    "type": "string";
    "required": False;
    "nullable": True;
  };
};

// Test per la funzione get
/*str:get_1 := get(data, "nome");
int:get_2 := get(data, "config.timeout");
str:get_3 := get(data, "versioni.0.status");
str:get_4 := get(data, "versioni.1.dettagli.tester");
list:get_5 := get(data, "versioni.*.status");
list:get_6 := get(data, "versioni.*.id");

// Test per la funzione format
str:format_1 := format("Ciao {{nome}}", nome: "Progetto A");

// Convert
int:convert_1 := convert("10", int);
str:convert_2 := convert(10, str);
bool:convert_3 := convert("true", bool);
bool:convert_4 := convert("false", bool);
str:convert_5 := convert(true, str);
str:convert_6 := convert(false, str);
//str:convert_7 := convert(True, bool);
//str:convert_8 := convert(False, bool);

// put 
dict:put_1 := put(data, "nome", "Progetto B");
//dict:put_2 := put(data, "versioni.1.status", "completo");
dict:put_3 := put(data, "config.timeout", 60);
//dict:put_4 := put(data, "versioni.*.status", "completo");
//dict:put_5 := put(data, "versioni.*.dettagli.tester", "Mario");

// normalize
dict:normalize_1 := normalize({
    "name": "Mario";
    "surname": "Rossi";
    "age": 30;
    "email": "[EMAIL_ADDRESS]";
    "phone": 1234567890;
    "address": "Via Roma 1";
}, user_schema);

// transform 
//any:transform_1 := transform({
//    "name": "Mario";
//    "surname": "Rossi";
//    "age": 30;
//    "email": "[EMAIL_ADDRESS]";
//    "phone": 1234567890;
//    "address": "Via Roma 1";
//}, { name: { model:"name"; user:"nome"; }; age: { model:"age"; user:"eta"; }; output: 30; }, { }, user_schema, utente_schema);

*/

// Test suite
tuple:test_suite := (
    { target: 'get'; args: [data, "nome"]; output: "Progetto A"; },
    { target: 'get'; args: [data, "config.timeout"]; output: 30; },
    { target: 'get'; args: [data, "versioni.0.status"]; output: "completo"; },
    { target: 'get'; args: [data, "versioni.1.dettagli.tester"]; output: "Mario"; },
    { target: 'get'; args: [data, "versioni.*.status"]; output: ["completo", "in_corso", "fallito"]; },
    { target: 'get'; args: [data, "versioni.*.id"]; output: [1, 2, 3]; },
    { target: 'format'; args: ["Ciao {{nome}}", nome: "Progetto A"]; output: "Ciao Progetto A"; },
    { target: 'convert'; args: ["10", int]; output: 10; },
    { target: 'convert'; args: [10, str]; output: "10"; },
    { target: 'convert'; args: ["true", bool]; output: True; },
    { target: 'convert'; args: ["false", bool]; output: False; },
    { target: 'convert'; args: [true, str]; output: "True"; },
    { target: 'convert'; args: [false, str]; output: "False"; },
);