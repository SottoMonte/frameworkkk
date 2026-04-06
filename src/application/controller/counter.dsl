{

  counter_logic : {
    // Valore corrente del counter (default 0, persiste in sessione)
    count: 0; 

    // Incrementa: aggiorna lo stato E rebuild del nodo UI in un'unica chiamata
    increment_btn() -> {
        "1": messenger.post(
            session: sid,
            domain: "counter:counter_logic.count",
            payload: (counter_logic.count + 1),
            node: "counter_display"
        ) ;
        "2": presenter.rebuild("counter_display", sid, {count: counter_logic.count});
    };

    decrement_btn() -> {
        "1": messenger.post(
            session: sid,
            domain: "counter:counter_logic.count",
            payload: (counter_logic.count - 1),
            node: "counter_display"
        ) ;
        "2": presenter.rebuild("counter_display", sid, {count: counter_logic.count});
    };
  }

}