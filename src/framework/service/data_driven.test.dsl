#int:numero:=10;int:zio:="ciao   1";int:cane:=10;

#int:entrata := 1000;
#int:uscita := entrata;

function:somma := (int:c,int:b),{x:c+b},(int:x);
marco: 10 / 2 + 10 ;
a:marco + 23;
#b:print("ciao  123");
#int:a := 10;
#int:b := a + 10;

#print("ciao  123");

int:x := 10000 - 9999;

ziooo:somma(10,-15);

ok: 23 |> somma(10);

ttt: a |> print;

ggg: resource |> print;

ooo: print(10);

imports: {
    'flow':resource("framework/service/flow.py");
};

tttt: imports.flow.step(print,1,2);
