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

any:cpu_ok    := @cpu < limits.cpu;
any:mem_ok    := @ram < limits.memory;
any:disk_ok   := @disk < limits.disk;

any:all_ok    := cpu_ok & mem_ok & disk_ok;
any:any_crit  :=  mem_ok | cpu_ok;

any:status := all_ok == true & messages.ok
           | any_crit == false & messages.critical
           | messages.warning;

health: {

    cpu(schedule:5) -> random(0,100);
    gpu(schedule:5) -> random(0,100);
    ram(schedule:5) -> random(0,100);
    disk(schedule:1) -> random(0,100);
    //check(deps_policy:3) -> print("######### CPU:",health.cpu,"% GPU:",gpu,"% RAM:",ram,"% DISK:",disk,"%");
    //alert(schedule:5,deps:['check'],when: any_crit) -> print("ATTENZIONE: SOGLIA SUPERATA");
};

/*ggg(schedule:5) -> print(health.cpu);
zzz(schedule:5) -> bios();
fff(schedule:5) -> health.cpu|>print("fff----->");
bdd(schedule:5) -> @health.cpu|>print("bdd----->");*/

/*pipeline_(schedule:5) -> {"cpu":health.cpu;"gpu":health.gpu;"ram":health.ram;"disk":health.disk} |> 
switch({
    @cpu > limits.cpu: "cpu limite superato";
    @gpu > 80:         "gpu limite superato";
    @ram > limits.memory: "ram limite superato";
    @disk > limits.disk:  "disk limite superato";
    true: "situazione normale";
}) |> print("@@@@@@@@@@@@@@@@@@@@");*/

//ggg(schedule:5) -> print(health.cpu);
test_schedule_duration(schedule:5,duration:10,default:0,on_close:integration_test) -> test_schedule_duration + 1;

test:{
    test_schedule_duration:{'outputs':2;'assert':true};
};

integration_test(default:test,meta:true) -> print("[*] Running integration test...",integration_test,"/100");

