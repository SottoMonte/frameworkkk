{
    include("constants.dsl");
    
    print_version : VERSION | print;
    
    test_match : "ACTION_A" | match({
        "@ == 'ACTION_A'": print;
        "@ == 'ACTION_B'": print;
    });

    data_list : ("A", "B", "C");
    
    # parallel is batch
    test_parallel : data_list | parallel(print);
}
