{
    # ============================================
    # DSL Feature Showcase
    # ============================================
    
    include("constants.dsl");
    
    # ============================================
    # 1. INCLUDE - Modularità
    # ============================================
    version_info : VERSION | print;
    app_name_info : APP_NAME | print;
    
    # ============================================
    # 2. MATCH/SWITCH - Branching Condizionale
    # ============================================
    environment : "production";
    
    # Match ritorna il valore associato alla condizione che matcha
    log_level_value : environment | match({
        "@ == 'production'": "INFO";
        "@ == 'development'": "DEBUG";
        "@ == 'test'": "TRACE";
        "true": "WARN";
    });
    
    log_level_print : log_level_value | print;
    
    # ============================================
    # 3. TRANSFORM - Manipolazione Dati
    # ============================================
    services_config : {
        "database": {"host": "localhost"; "port": 5432;};
        "cache": {"host": "localhost"; "port": 6379;};
        "queue": {"host": "localhost"; "port": 5672;};
    };
    
    service_list : services_config | items | transform({
        "name": "@.0";
        "host": "@.1.host";
        "port": "@.1.port";
    }) | print;
    
    # ============================================
    # 4. KEYS/VALUES/ITEMS - Estrazione Dati
    # ============================================
    service_names : services_config | keys | print;
    
    # ============================================
    # 5. FILTER - Selezione Dati
    # ============================================
    filtered_services : services_config | filter(("database", "cache")) | print;
    
    # ============================================
    # Summary
    # ============================================
    summary : {
        "version": VERSION;
        "app": APP_NAME;
        "environment": environment;
        "log_level": log_level_value;
        "services": service_names;
    } | print;
}
