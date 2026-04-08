type:route := {
    "path": { "type": "string" };
    "method": { "type": "string"; "default": "GET" };
    "type": { "type": "string" };
    "view": { "type": "string"; "default": "" };
};

type:policy := {
    "id": { "type": "string" };
    "effect": { "type": "string"; "default": "GET" };
    "match": { "type": "string" };
    "description": { "type": "string"; "default": "" };
    "condition": { "type": "string"; "default": "" };
    "type": { "type": "string"; "default": ""; "regex": "^(ABAC|RBAC|PBAC|MAC)$" };
};

function:check_abac := (dict:user, dict:resource, dict:env){
    // Esempio: l'utente può modificare la risorsa solo se ne è il proprietario
    // o se è in orario di ufficio
    is_owner: user.id == resource.owner_id;
    is_office_hours: env.hour >= 9 & env.hour <= 18;
    
    authorized: is_owner or (user.role == "staff" & is_office_hours);
}(bool:authorized);



routes: {
    route:GET_INDEX := { path:"/"; method:"GET"; "type":"view"; view:"auth/login.xml" };
    route:GET_PROFILE := { path:"/profile"; method:"GET"; "type":"view"; view:"profile.xml" };
    route:GET_LOGIN := { path:"/login"; method:"GET"; "type":"view"; view:"login.xml" };
    route:GET_LOGOUT := { path:"/logout"; method:"GET"; "type":"view"; view:"logout.xml" };
    route:GET_ADMIN := { path:"/admin"; method:"GET"; "type":"view"; view:"admin.xml" };
}

policies: {
    policy:GET_INDEX := {id:"policy-1"; effect:"allow"; match:"/" ;description:"Allow access to /"; condition:"true"; "type":"ABAC";};
}
    
