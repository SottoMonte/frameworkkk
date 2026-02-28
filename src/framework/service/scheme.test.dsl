exports: {
    "get": get;
    "format": format;
    "convert": convert;
    "put": put;
    "normalize": normalize;
    "transform": transform;
};

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

/*
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
    { target: "exports.get"; inputs: [data, "nome"]; output: "Progetto A"; },
    { target: "exports.get"; inputs: [data, "config.timeout"]; output: 30; },
    { target: "exports.get"; inputs: [data, "versioni.0.status"]; output: "completo"; },
    { target: "exports.get"; inputs: [data, "versioni.1.dettagli.tester"]; output: "Mario"; },
    { target: "exports.get"; inputs: [data, "versioni.*.status"]; output: ["completo", "in_corso", "fallito"]; },
    { target: "exports.get"; inputs: [data, "versioni.*.id"]; output: [1, 2, 3]; },
    { target: "exports.format"; inputs: ["Ciao {{nome}}", nome: "Progetto A"]; output: "Ciao Progetto A"; },
    { target: "exports.convert"; inputs: ["10", int]; output: 10; },
    { target: "exports.convert"; inputs: [10, str]; output: "10"; },
    { target: "exports.convert"; inputs: ["true", bool]; output: True; },
    { target: "exports.convert"; inputs: ["false", bool]; output: False; },
    { target: "exports.convert"; inputs: [true, str]; output: "True"; },
    { target: "exports.convert"; inputs: [false, str]; output: "False"; },
    //{ target: "exports.put"; inputs: [data, "nome", "Progetto B"]; "filter":"nome"; output: "Progetto B"; },
    //{ target: "exports.put"; inputs: [data, "config.timeout", 60]; "filter":"config.timeout"; output: 60; },
    //{ target: "exports.put"; inputs: [data, "versioni.0.status", "completo"]; "filter":"versioni.0.status"; output: "completo"; },
    //{ target: "exports.put"; inputs: [data, "versioni.1.dettagli.tester", "Mario"]; "filter":"versioni.1.dettagli.tester"; output: "Mario"; },
    //{ target: "exports.put"; inputs: [data, "versioni.*.status", "completo"]; "filter":"versioni.*.status"; output: ["completo", "completo", "completo"]; },
    //{ target: "exports.put"; inputs: [data, "versioni.*.id", 1]; "filter":"versioni.*.id"; output: [1, 1, 1]; },
    //{ target: "exports.normalize"; inputs: [{"name": "Mario"; "surname": "Rossi"; "age": 30; "email": "[EMAIL_ADDRESS]"; "phone": 1234567890; "address": "Via Roma 1"}, user_schema]; output: {"name": "Mario"; "surname": "Rossi"; "age": 30; "email": "[EMAIL_ADDRESS]"; "phone": 1234567890; "address": "Via Roma 1"}; },
    
);