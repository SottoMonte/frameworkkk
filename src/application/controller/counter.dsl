{

  counter_logic : {
    // Valore corrente del counter (default 0, persiste in sessione)
    count(default: 0, on_start:"counter_logic.update") -> counter_logic.count;
    update(deps:false) -> presenter.rebuild("counter_display", sid, {count: counter_logic.count});
    //count: 0;
    
    
    // Incrementa: aggiorna lo stato E rebuild del nodo UI in un'unica chiamata
    increment_btn(deps:false) -> messenger.post(
      session: sid,
      domain: "counter:counter_logic.count",
      payload: (counter_logic.count + 1),
      node: "counter_display"
    );

    decrement_btn(deps:false) -> messenger.post(
      session: sid, 
      domain: "counter:counter_logic.count", 
      payload: (counter_logic.count - 1), 
      node: "counter_display"
    );
  }

}