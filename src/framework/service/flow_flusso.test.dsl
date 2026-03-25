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
test_schedule_duration(schedule:2,duration:10,default:1,on_close:data,on_end:report) -> test_schedule_duration + 1;


data(meta:true) -> data;

tests:{
    test_schedule_duration:{'outputs':2;'assert':@loop == 5 & @outputs == 6;'loop':0;'max_loop':5};
};

integration_test(default:tests) -> integration_test |> test:get(data.trigger) |> reset(integration_test) |> put(data.trigger+".loop", test.loop + 1) |> put(data.trigger+".outputs", data.outputs);
/*|> 
switch({
    //@assert: @reset(print("[O] test superato "+data.trigger),integration_test);
    //@loop == @max_loop: @reset(print("[X] test fallito "+data.trigger),integration_test);
    true: integration_test 
});*/
// put(data.trigger+".loop", test.loop + 1)

report(default:tests) -> integration_test |> test:get(data.trigger) |> 
switch({
    @assert: @print("[O] test superato "+data.trigger);
    @loop == @max_loop: @print("[X] test fallito "+data.trigger);
});

//aaa() -> print(integration_test);
