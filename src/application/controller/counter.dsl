{
  /*counter_logic : {
    count : 0;
    increment_btn(schedule:2) -> count + 1 |> print;
    decrement_btn(schedule:2) -> count - 1 |> print;
  };*/
  aaaa:10;
  CCCC:print(presenter.rebuild);
  iuds:print(sid);
  zzz:presenter.rebuild("counter_display",sid,{count:aaaa});
  increment_btn(schedule:2) -> aaaa + 1 |> print;
}