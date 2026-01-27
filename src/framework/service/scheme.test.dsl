# Test per la funzione get
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

# Test per la funzione get
str:get_1 := get(data, "nome");
int:get_2 := get(data, "config.timeout");
str:get_3 := get(data, "versioni.0.status");
str:get_4 := get(data, "versioni.1.dettagli.tester");
list:get_5 := get(data, "versioni.*.status");
list:get_6 := get(data, "versioni.*.id");

# Test per la funzione format
str:format_1 := format("Ciao {{nome}}", nome: "Progetto A");


# Test suite
tuple:test_suite := (
    { target: 'get_1'; output: "Progetto A"; },
    { target: 'get_2'; output: 30; },
    { target: 'get_3'; output: "completo"; },
    { target: 'get_4'; output: "Mario"; },
    { target: 'get_5'; output: ["completo", "in_corso", "fallito"]; },
    { target: 'get_6'; output: [1, 2, 3]; },
    { target: 'format_1'; output: "Ciao Progetto A"; },
);