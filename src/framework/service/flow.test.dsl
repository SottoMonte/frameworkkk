imports: {
    'contract': 'framework/service/contract.py';
};

exports: {
    'asynchronous': 'asynchronous';
    'synchronous': 'synchronous';
    'format': 'format';
    'transform': 'transform';
    'convert': 'convert';
    'route': 'route';
    'normalize': 'normalize';
    'put': 'put';
    'get': 'get';
    'work': 'work';
    'step': 'step';
    'pipe': 'pipe';
    'catch': 'catch';
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

any:get(data,nome)|print;

tuple:test_suite := (
);