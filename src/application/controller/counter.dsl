{
  counter_logic : {
    count : 0;
    increment_btn.click() -> {
       count : count + 1;
       zio:ui.refresh("counter_text");
    };
    decrement_btn.click() -> {
       count : count - 1;
       zio:ui.refresh("counter_text");
    };
  };
}