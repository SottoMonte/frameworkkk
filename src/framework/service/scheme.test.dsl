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
    {
        "action": exports.get;
        "inputs":(data, "nome");
        "outputs": "Progetto A";
        "assert": @received == @expected;
        "note": "get";
    },
    {
        "action": exports.get;
        "inputs":(data, "config.timeout");
        "outputs": 30;
        "assert": @received == @expected;
        "note": "get";
    },
    {
        "action": exports.get;
        "inputs":(data, "versioni.0.status");
        "outputs": "completo";
        "assert": @received == @expected;
        "note": "get";
    },
    {
        "action": exports.get;
        "inputs":(data, "versioni.1.dettagli.tester");
        "outputs": "Mario";
        "assert": @received == @expected;
        "note": "get";
    },
    {
        "action": exports.get;
        "inputs":(data, "versioni.*.status");
        "outputs": ["completo", "in_corso", "fallito"]; 
        "assert": @received == @expected;
        "note": "get";
    },
    {
        "action": exports.get;
        "inputs":(data, "versioni.*.id");
        "outputs": [1, 2, 3]; 
        "assert": @received == @expected;
        "note": "get";
    },
    {
        "action": exports.format;
        "inputs":{"target":"Ciao {{nome}}";"nome":"Progetto A"};
        "outputs": "Ciao Progetto A";
        "assert": @received == @expected;
        "note": "format";
    },
    {
        "action": exports.convert;
        "inputs":("10", int);
        "outputs": 10;
        "assert": @received == @expected;
        "note": "convert";
    },
    {
        "action": exports.convert;
        "inputs":(10, str);
        "outputs": "10";
        "assert": @received == @expected;
        "note": "convert";
    },
    {
        "action": exports.convert;
        "inputs":("true", bool);
        "outputs": True;
        "assert": @received == @expected;
        "note": "convert";
    },
    {
        "action": exports.convert;
        "inputs":("false", bool);
        "outputs": False;
        "assert": @received == @expected;
        "note": "convert";
    },
    {
        "action": exports.convert;
        "inputs":(true, str);
        "outputs": "True";
        "assert": @received == @expected;
        "note": "convert";
    },
    {
        "action": exports.convert;
        "inputs":(false, str);
        "outputs": "False";
        "assert": @received == @expected;
        "note": "convert";
    },
    {
        "action": exports.put;
        "inputs":(data, "nome", "Progetto B");
        "outputs": "Progetto B";
        "assert": @received.nome == @expected;
        "note": "put";
    },
    {
        "action": exports.put;
        "inputs":(data, "config.timeout", 60);
        "outputs": 60;
        "assert": @received.config.timeout == @expected;
        "note": "put";
    },
    /*{
        "action": exports.put;
        "inputs":(data, "versioni.0.status", "completo");
        "outputs": "completo";
        "assert": @received.versioni.0.status == @expected;
        "note": "put";
    },*/
    {
        "action": exports.put;
        "inputs":(data, "versioni.1.dettagli.tester", "Mario");
        "outputs": "Mario";
        "assert": @received == @expected;
        "note": "put";
    },
    {
        "action": exports.put;
        "inputs":(data, "versioni.*.status", "completo");
        "outputs": ["completo", "completo", "completo"]; 
        "assert": @received.versioni.0.status == @expected;
        "note": "put";
    },
    {
        "action": exports.put;
        "inputs":(data, "versioni.*.id", 1);
        "outputs": [1, 1, 1]; 
        "assert": @received == @expected;
        "note": "put";
    },
    //{ target: "exports.normalize"; inputs: [{"name": "Mario"; "surname": "Rossi"; "age": 30; "email": "[EMAIL_ADDRESS]"; "phone": 1234567890; "address": "Via Roma 1"}, user_schema]; output: {"name": "Mario"; "surname": "Rossi"; "age": 30; "email": "[EMAIL_ADDRESS]"; "phone": 1234567890; "address": "Via Roma 1"}; },
    
);