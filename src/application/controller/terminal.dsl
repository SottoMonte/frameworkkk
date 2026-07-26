{
    selected: "src/infrastructure/presentation/console.py";
    dependencies: loader.file_dependencies(selected);
    
    files: storekeeper.overview(sid, repository: "file",filter: {"startswith":{"relative_path": "/src"};"eq": {"type": "file"}});

    editor: {
        application:storekeeper.gather(sid, repository: "file",filter: {"eq": {"filename": get(dependencies,"0")}});
        framework:storekeeper.gather(sid, repository: "file",filter: {"eq": {"filename": get(dependencies,"1")}});
        infrastructure:storekeeper.gather(sid, repository: "file",filter: {"eq": {"filename": get(dependencies,"2")}});
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