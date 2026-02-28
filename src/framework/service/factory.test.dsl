{
    //tuple:tuple_void := ();
    //tuple:tuple_full := (1,2,3);
    //tuple:tuple_inline := 5,6,7;

    //x,y,z : tuple_full;
    //int:x,int:y,int:z := tuple_full;
    x,y,z : 1,2,"ciao";
    a,b,c : x,y,z;
    cc:print(a,b,c);
    cc:print(x,y,z);
    cc:"1,2,3" |> print("ciaone");
}
