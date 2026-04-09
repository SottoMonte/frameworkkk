type:route := {
    "path": { "type": "string" };
    "method": { "type": "string"; "default": "GET" };
    "type": { "type": "string" };
    "view": { "type": "string"; "default": "" };
    "controller": { "type": "string"; "default": "" };
};

type:policy := {
    "effect": { "type": "string"; "regex": "^(allow|deny)$"; "default": "deny" };
    "target": { 
        "schema": { "action": { "type": "string" }; "resource": { "type": "string" }; "location": { "type": "string" }; "context": { "type": "dict" } }; 
        "default": { "action": ""; "resource": ""; "location": ""; "context": {} };
    };
    "description": { "type": "string"; "default": "" };
    "condition": { "default": true };
};

type:user := {
  "identifier": { "type": "string" };
  "username": { "type": "string" };
  "role": { "type": "string"; "regex": "^(admin|user|guest)$" };
  "avatar": { "type": "string" };
};

type:role := {
    "id": { "type": "string" };
    "name": { "type": "string" };
    "description": { "type": "string" };
    "resources": { "type": "list"; "schema": { "type": "string" } };
};

roles:{
    role:admin := {
        id:"role-1";
        name:"admin";
        description:"admin";
        resources:["all"];
    };
    role:user := {
        id:"role-2";
        name:"user";
        description:"user";
        resources:["all"];
    };
    role:guest := {
        id:"role-3";
        name:"guest";
        description:"guest";
        resources:["application/view/page/auth/login.xml"];
    };
}

routes: {
    route:GET_INDEX := { path:"/"; method:"GET"; "type":"view"; view:"auth/login.xml"; controller:"tris" };
    route:GET_PROFILE := { path:"/profile"; method:"GET"; "type":"view"; view:"profile.xml" };
    route:GET_LOGIN := { path:"/login"; method:"GET"; "type":"view"; view:"login.xml" };
    route:GET_LOGOUT := { path:"/logout"; method:"GET"; "type":"view"; view:"logout.xml" };
    route:GET_ADMIN := { path:"/admin"; method:"GET"; "type":"view"; view:"admin.xml" };
    route:GET_ERROR_404 := { path:"/404"; method:"GET"; "type":"view"; view:"error/404.xml" };
    route:GET_BROWSER := { path:"/browse"; method:"GET"; "type":"view"; view:"twitch_browse.xml" };
    route:GET_HOME := { path:"/home"; method:"GET"; "type":"view"; view:"twitch_home.xml" };
    route:GET_USER_PROFILE := { path:"/user/{id}"; method:"GET"; "type":"view"; view:"twitch_channel.xml" };
    route:GET_TRIS := { path:"/tris"; method:"GET"; "type":"view"; view:"tris.xml"; controller:"tris" };
}

policies: {
    policy:GET_ALLOW_PATH := {
        effect:"allow";
        target: { action: "GET"; };
        description:"Allow GET method for resources in guest role"; 
        condition: (@resource in roles.guest.resources) & (@action == "GET");
    };
    policy:GET_ALLOW_ALL := {
        effect:"allow";
        target: { action: "GET"; };
        description:"Allow all GET requests";
        condition: @action == "GET";
    };
}
    

rules : {
    "/": [policies.GET_ALLOW_PATH];
    "/profile": [policies.GET_ALLOW_PATH];
    "/login": [policies.GET_ALLOW_PATH];
    "/logout": [policies.GET_ALLOW_PATH];
    "/admin": [policies.GET_ALLOW_PATH];
    "/browse": [policies.GET_ALLOW_ALL];
    "/home": [policies.GET_ALLOW_ALL];
    "/user/{id}": [policies.GET_ALLOW_ALL];
    "/tris": [policies.GET_ALLOW_ALL];
    "/static/js/dsl.js": [policies.GET_ALLOW_ALL];
    //"/404": [policies.GET_ALLOW_ALL];
}
