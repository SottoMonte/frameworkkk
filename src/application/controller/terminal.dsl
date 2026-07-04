{
    a:"asaas";
    dire: storekeeper.overview("asdasd", repository: "file",filter: {"type": {"eq": "file"}});
    //close(deps:false) -> exit();
    //submit(deps:false) -> messenger.post(sid, domain: "console:info", message: submit);
    //stampa() -> [storekeeper.overview(sid, repository: "file",filter: {"type": {"eq": "file"}}),exit(1)];
    //stampa() -> messenger.post(sid, domain: "console:info", message:   dire);
    cmd:{
        //close(deps:false) -> messenger.post(sid, domain: "console:error", message: "ciao");
    };
}