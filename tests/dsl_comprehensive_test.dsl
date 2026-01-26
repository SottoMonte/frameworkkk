{
    # 1. Variabili di base
    int:base := 10;
    int:moltiplicatore := 5;
    str:prefisso := "RISULTATO:";
    
    # 2. Funzioni Matematiche
    function:quadrato := (int:n), { 
        r: n * n; 
    }, (int:r);
    
    function:calcolo_complesso := (int:x, int:y), { 
        prodotto: x * y;
        somma: x + y;
        differenza: x - y;
        # Restituiamo un dizionario come risultato complesso
        r: { "p": prodotto; "s": somma; "d": differenza; };
    }, (dict:r);

    # 3. Funzioni di Logica e Stringhe
    function:valida_e_formatta := (int:valore, str:msg), {
        # Test condizionale via switch/match
        status: valore |> match({
            "@ > 50": "ALTO";
            "@ <= 50": "BASSO";
        });
        
        r: prefisso + " " + msg + " -> " + status;
    }, (str:r);

    # 4. Collezioni
    list:numeri := [1, 2, 3, 4, 5];
    dict:mappa_base := { "a": 1; "b": 2; };
    
    # 5. Operazioni di Test (Target)
    
    # Test Precedenza e Operatori
    int:test_math_precedence := (10 + 2 * 5) / 2; # (10 + 10) / 2 = 10
    
    # Test Pipe Chaining
    int:test_pipe_chain := 2 |> quadrato |> quadrato; # 2 -> 4 -> 16
    
    # Test Chiamata Funzione con Dict return
    dict:test_func_dict := calcolo_complesso(10, 5); # { "p": 50, "s": 15, "d": 5 }
    
    # Test Logica Complessa
    boolean:test_logic_complex := (Vero | Falso) & (10 > 5) & (not (1 == 2));
    
    # Test Switch/Match
    str:test_match_direct := 75 |> match({
        "@ >= 90": "A";
        "@ >= 70": "B";
        "@ < 70": "C";
    });
    
    # Test Operazioni su Collezioni (Standard Library)
    dict:test_merge := merge({ "x": 10; }, { "y": 20; });
    list:test_concat := concat([1, 2], [3, 4]);
    dict:test_pick := { "nome": "Mario"; "eta": 30; } |> pick(["nome"]);

    # 6. TEST SUITE
    list:test_suite := [
        { "target": "test_math_precedence"; "expected_output": 10; "description": "Precedenza aritmetica corretta"; },
        { "target": "test_pipe_chain"; "expected_output": 16; "description": "Chain di pipe multiple"; },
        { "target": "test_func_dict"; "expected_output": { "p": 50; "s": 15; "d": 5; }; "description": "Ritorno di dizionario da funzione"; },
        { "target": "test_logic_complex"; "expected_output": Vero; "description": "Logica booleana con NOT e raggruppamento"; },
        { "target": "test_match_direct"; "expected_output": "B"; "description": "Controllo di flusso via match"; },
        { "target": "test_merge"; "expected_output": { "x": 10; "y": 20; }; "description": "Funzione standard merge"; },
        { "target": "test_concat"; "expected_output": [1, 2, 3, 4]; "description": "Funzione standard concat"; },
        { "target": "test_pick"; "expected_output": { "nome": "Mario"; }; "description": "Funzione standard pick su dizionario"; },
        { "target": "valida_e_formatta"; "input_args": [60, "Test"]; "expected_output": "RISULTATO: Test -> ALTO"; "description": "Funzione complessa con match e concatenazione stringhe"; }
    ];
}
