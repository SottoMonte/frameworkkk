Prism.languages.dsl = {
    // 1. Commenti e Stringhe (Priorità massima)
    'comment': /\/\/.*/,
    'string': {
        pattern: /(["'])(?:\\.|(?!\1)[^\\\r\n])*\1/,
        greedy: true
    },

    // 2. Entity (Keywords di sistema)
    // Devono essere seguite da ":", "{" o ":=" per essere riconosciute come definizioni
    'entity': {
        pattern: /\b(?:type|role|route|policy|roles|routes|policies|rules|any|imports|exports|tuple)\b(?=\s*(?::|[:=]|\{))/i,
        alias: 'keyword'
    },

    // 3. Decoratori e Variabili Speciali (es. @auth.check)
    'variable-special': {
        pattern: /@\w+(?:\.\w+)*/,
        alias: 'important' // Cambiato in 'important' per risaltare rispetto alle funzioni
    },

    // 4. Chiamate di Funzione (es. hasRole(.. )
    'function': {
        pattern: /\b\w+(?:\.\w+)*(?=\s*\()/,
        alias: 'attr-name'
    },

    // 5. Costanti
    'boolean': /\b(?:true|false)\b/,
    'number': /\b\d+(?:\.\d+)?\b/,

    // 6. Operatori e Punteggiatura
    'operator': /:=|&&|\|\||[&|<>!=]=?|[-+*/%]|==/,
    'punctuation': /[{}[\];(),.:]/,

    // 7. Property (Chiavi di dizionario o attributi)
    // Esempio: "roles:" o route:
    'property': {
        pattern: /\b\w+(?=\s*:)|(["'])(?:\\.|(?!\1)[^\\\r\n])*\1(?=\s*:)/,
        greedy: true,
        alias: 'symbol'
    },

    // 8. Variable (Identificatori generici)
    // Tutto ciò che non è stato catturato sopra (nomi di tipi, parametri, ecc.)
    'variable': {
        pattern: /\b\w+(?:\.\w+)*\b/,
        alias: 'parameter'
    }
};