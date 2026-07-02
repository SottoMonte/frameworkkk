{
    close(deps:false) -> messenger.test();
  
  cmd:{
    close(deps:false) -> messenger.post(sid, domain: "console:error", message: "ciao");
  };
}