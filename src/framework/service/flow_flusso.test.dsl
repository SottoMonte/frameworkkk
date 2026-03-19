imports: {
    'flow':resource("framework/service/flow." + extension);
};

exports: {
    'assert': imports.flow.assertt;
    'foreach': imports.flow.foreach;
    'pass': imports.flow.passs;
    'catch':  imports.flow.catch;
    'serial': imports.flow.serial;
    'parallel': imports.flow.parallel;
    'retry': imports.flow.retry;
    'pipeline': imports.flow.pipeline;
    'guard': imports.flow.guard;
    'switch': imports.flow.switch;
    'when': imports.flow.when;
    'timeout': imports.flow.timeout;
};

// soglie e configurazione
dict:limits := {
    "cpu":    80;
    "memory": 90;
    "disk":   95;
};

dict:messages := {
    "ok":       "tutti i sistemi operativi";
    "warning":  "attenzione: soglia superata";
    "critical": "critico: intervento richiesto";
};

any:cpu_ok    := @level > limits.cpu;
any:mem_ok    := @level > limits.memory;
any:disk_ok   := @level > limits.disk;

any:all_ok    := cpu_ok & mem_ok & disk_ok;
any:any_crit  := cpu_ok | mem_ok;

any:status := all_ok == true & messages.ok
           | any_crit == false & messages.critical
           | messages.warning;

function:error_function := (str:y){
    x:y/2;
}(str:x);

function:success_function := (str:y){x:y;}(str:x);

health: {

    level(schedule:5) -> random(0,100);
    gpu(schedule:5) -> random(0,100);
    ram(schedule:5) -> @random(0,100);
    disk(schedule:1) -> random(0,100);
    check(deps:['level','gpu','ram','disk'],deps_policy:3) -> print("######### CPU:",level,"% GPU:",gpu,"% RAM:",ram,"% DISK:",disk,"%");
    //alert(schedule:5,when: all_ok) -> print("ATTENZIONE: SOGLIA SUPERATA");
};

tuple:test_suite := (
    { 
        "action": exports.assert;
        "inputs":(@numero <= 50, {numero:60});
        "outputs": None;
        "assert": @received.outputs == @expected & @received.success == false;
        "note": "assert false + context"; 
    },
);