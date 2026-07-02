{
    "123":"ciao";
    close(deps:false) -> messenger.test();
  
  cmd:{
    close(deps:false) -> messenger.post(session: sid, domain: "console:error", payload: {});
  };
}