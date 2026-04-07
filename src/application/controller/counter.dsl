{

  counter_logic : {
    // Valore corrente del counter (default 0, persiste in sessione)
    count(default: 0) -> counter_logic.count;
    
    // Incrementa: aggiorna SOLO lo stato
    increment_btn(deps:false) -> messenger.post(
      session: sid,
      domain: "counter:counter_logic.count",
      payload: (counter_logic.count + 1)
    );

    // Decrementa: aggiorna SOLO lo stato
    decrement_btn(deps:false) -> messenger.post(
      session: sid, 
      domain: "counter:counter_logic.count", 
      payload: (counter_logic.count - 1)
    );
  }

}