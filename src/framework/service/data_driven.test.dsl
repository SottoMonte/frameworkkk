{
    # 1. Stato iniziale
    int:counter := 0;
    
    # 2. Definizione di un observer
    function:on_counter_change := (int:new_val), {
        print("REACTIVE UPDATE: counter is now " + convert(new_val, str));
    }, (any:res);

    # 3. Registrazione dell'osservazione
    observe("counter", on_counter_change);

    # 4. Suite di test
    list:test_suite := [
        { "target": "trigger_change"; "output": 10; "description": "Test set reattivo"; }
    ];

    # 5. Azione che scatena il cambiamento
    function:trigger_change := (), {
        set("counter", 10);
        r: 10;
    }, (int:r);
}
