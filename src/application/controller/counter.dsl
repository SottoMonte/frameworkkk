{

  counter_logic : {
    // Recuperiamo il valore corrente o usiamo 0 come default
    count: 11; 

    // Quando arriva il trigger 'increment_btn', calcola count+1 e rinfresca la UI
    increment_btn() -> presenter.rebuild("counter_display", sid, {count: 12});

    // Quando arriva il trigger 'decrement_btn', calcola count-1 e rinfresca la UI
    decrement_btn() -> presenter.rebuild("counter_display", sid, {count: 11});
  };

  increment_btn() -> presenter.rebuild("counter_display", sid, {count: 9});
  decrement_btn() -> presenter.rebuild("counter_display", sid, {count: 8});

}