{
    close(deps:false) -> exit();
    submit(deps:false) -> messenger.post(sid, domain: "console:info", message: submit);
  
    cmd:{
        close(deps:false) -> messenger.post(sid, domain: "console:error", message: "ciao");
    };
}