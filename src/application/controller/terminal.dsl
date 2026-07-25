{
    
    editor: {
        application:storekeeper.gather(sid, repository: "file",filter: {"eq": {"filename": "application/controller/terminal.dsl"}});
        framework:storekeeper.gather(sid, repository: "file",filter: {"eq": {"filename": "application/controller/terminal.dsl"}});
        infrastructure:storekeeper.gather(sid, repository: "file",filter: {"eq": {"filename": "application/controller/terminal.dsl"}});
    };
    //close(deps:false) -> exit();
    submit(deps:false) -> messenger.post(sid, domain: "console:info", message: submit);
    //stampa() -> [storekeeper.overview(sid, repository: "file",filter: {"type": {"eq": "file"}}),exit(1)];
    stampa(deps:false) -> messenger.post(sid, domain: "console:info", message:   dire);
    new(deps:false) -> presenter.rebuild("editor-application",sid);
    cmd:{
        //new(deps:false) -> presenter.rebuild("editor-application",sid);
        close(deps:false, entry:false) -> exit(1);
        //close(deps:false) -> messenger.post(sid, domain: "console:error", message: "ciao");
    };
}