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
any:any_crit  := cpu_ok | mem_ok;

any:status := all_ok == true & messages.ok
           | any_crit == false & messages.critical
           | messages.warning;

//aaac:print(all_ok(level:100));
//aaa:print(all_ok(level:0));
//CCC:@random(1,10);
//zzz:print(CCC);
//zzz1:print(CCC);
// pipeline
/*health: {
    check(every: 10) -> print(status);
    report(every: 60) -> print(messages.ok);
    alert(on: threshold_exceeded) -> print(messages.critical);
    sync(every: 30, on: 'force') -> print("sync");
};*/

function:report := (int:level){
    msg:level;
    aaa:"print(msg)";
}(str:msg);



//aaa:print(status(level:100));
//aaa:print(report(100));

//level(schedule:5) -> random(0,100);

health: {

    level() -> random(0,100);
    gpu() -> random(0,100);
    ram() -> @random(0,100);
    memory() -> random(0,100);
    disk() -> random(0,100);
    check(schedule:5,triggers:['level','gpu','ram','memory','disk']) -> print("############# CPU:",level,"% GPU:",gpu,"% RAM:",ram,"% MEMORY:",memory,"% DISK:",disk,"%");
    //alert() -> report(level:level);
    /*report(schedule:60,triggers:[level]) -> print;
    alert(on: threshold_exceeded,triggers:[level]) -> print;
    sync(schedule:30,triggers:[level]) -> print;*/
};


tuple:test_suite := (

);