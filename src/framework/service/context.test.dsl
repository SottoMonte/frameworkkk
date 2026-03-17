// Test suite

a : 1;
a : 2;

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
int:level := 0;

bool:cpu_ok    := level < limits.cpu;
bool:mem_ok    := level < limits.memory;
bool:disk_ok   := level < limits.disk;

bool:all_ok    := cpu_ok & mem_ok & disk_ok;
bool:any_crit  := (not cpu_ok) | (not mem_ok);

str:status := all_ok == true & messages.ok
           | any_crit == true & messages.critical
           | messages.warning;

// pipeline
/*health: {
    check(every: 10) -> print(status);
    report(every: 60) -> print(messages.ok);
    alert(on: threshold_exceeded) -> print(messages.critical);
    sync(every: 30, on: 'force') -> print("sync");
};*/

health: {
    check(every: "1s",depends_on:[aaa]) -> print;
};

tuple:test_suite := (

);