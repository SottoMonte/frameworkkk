// Test suite

// soglie e configurazione
dict:limits := {
    "cpu":    80.0;
    "memory": 90.0;
    "disk":   95.0;
};

dict:messages := {
    "ok":       "tutti i sistemi operativi";
    "warning":  "attenzione: soglia superata";
    "critical": "critico: intervento richiesto";
};

// logica di valutazione
any:level := random(0,100);

any:cpu_ok    := @level < limits.cpu;
any:mem_ok    := @level < limits.memory;
any:disk_ok   := @level < limits.disk;

any:all_ok    := cpu_ok & mem_ok & disk_ok;
any:any_crit  := (not cpu_ok) | (not mem_ok);

/*bool:status := all_ok == true & messages.ok
           | any_crit == true & messages.critical
           | messages.warning;*/

aaac:print(all_ok(level:100));
aaa:print(all_ok(level:0));
CCC:@random(1,10);
zzz:print(CCC);
zzz1:print(CCC);
// pipeline
/*health: {
    check(every: 10) -> print(status);
    report(every: 60) -> print(messages.ok);
    alert(on: threshold_exceeded) -> print(messages.critical);
    sync(every: 30, on: 'force') -> print("sync");
};*/



tuple:test_suite := (

);