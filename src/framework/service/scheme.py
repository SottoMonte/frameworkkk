import re
import json
import tomli
import hashlib
import copy
from urllib.parse import urlparse, urlencode
from jinja2 import Environment
from cerberus import Validator
from framework.service.diagnostic import LogReportEncoder, framework_log, buffered_log, _load_resource
from collections.abc import Mapping

mappa = {
    (str,dict,''): lambda v: v if isinstance(v, dict) else {},
    (dict,dict,''): lambda v: v,
    (str,str,''): lambda v: v,
    (str,dict,'json'): lambda v: json.loads(v) if isinstance(v, str) else v if isinstance(v, dict) else {},
    (dict,dict,'json'): lambda v: v,
    (dict,str,'json'): lambda v: json.dumps(v,indent=4,cls=LogReportEncoder) if isinstance(v, dict) else v if isinstance(v, str) else '',
    (str,str,'json'): lambda v: v,
    (str,str,'hash'): lambda v: hashlib.sha256(v.encode('utf-8')).hexdigest() if isinstance(v, str) else '',
    (str,dict,'toml'): lambda content: tomli.loads(content) if isinstance(content, str) else content if isinstance(content, dict) else {},
    (dict,dict,'toml'): lambda v: v,
    (dict,str,'toml'): lambda data: tomli.dumps(data) if isinstance(data, dict) else data if isinstance(data, str) else '',
    (str,str,'toml'): lambda v: v,
    (str,int,''): lambda v: int(v) if isinstance(v, str) else v if isinstance(v, int) else 0,
    (int,str,''): lambda v: str(v) if isinstance(v, int) else v if isinstance(v, str) else '',
    (str,bool,''): lambda v: True if v.lower() == 'true' else False,
    (bool,str,''): lambda v: str(v) if isinstance(v, bool) else v if isinstance(v, str) else '',
    (str,list,''): lambda v: [v],
    (type(None),list,''): lambda v: [],
}

async def convert(target, output,input=''):
    try:
        if type(target) == output:
            return target
        return mappa[(type(target),output,input)](target)
    except KeyError:
        raise ValueError(f"Conversione non supportata: {type(target)} -> {type(output)}:{output} da {input}")
    except Exception as e:
        raise ValueError(f"Errore conversione: {e}")

async def format(target ,**constants):
    try:
        jinjaEnv = Environment()
        jinjaEnv.filters['get'] = lambda d, k, default=None: d.get(k, default) if isinstance(d, (dict, Mapping)) else default
        template = jinjaEnv.from_string(target)
        return template.render(constants)
    except Exception as e:
        raise ValueError(f"Errore formattazione: {e}")

async def normalize(value, schema, mode='full'):
    """
    Convalida, popola, trasforma e struttura i dati utilizzando uno schema Cerberus.
    """
    value = value or {}

    if not isinstance(schema, Mapping):
        raise TypeError("Lo schema deve essere un dizionario valido per Cerberus.",schema)
    if not isinstance(value, Mapping):
        raise TypeError("I dati devono essere un dizionario valido per Cerberus.",value)

    # 1. Popolamento e Trasformazione Iniziale
    processed_value = value
    '''for key in schema.copy():
        item = schema[key]
        for field_name, field_rules in item.copy().items():
            if field_name.startswith('_'):
                schema.get(key).pop(field_name)'''

    for field_name, field_rules in schema.copy().items():
        value = processed_value.get(field_name)
        if isinstance(field_rules, dict) and 'function' in field_rules:
            func_name = field_rules['function']
            if func_name == 'generate_identifier':
                if field_name not in processed_value:
                    pass
            elif func_name == 'time_now_utc':
                if field_name not in processed_value:
                    pass
        if isinstance(field_rules, dict) and "convert" in field_rules:
            convert_name = field_rules["convert"]

            if field_name in processed_value:
                processed_value[field_name] = await convert(value, convert_name)

            schema[field_name].pop("convert")

    # Cerberus Validation
    v = Validator(schema,allow_unknown=True)

    if not v.validate(processed_value):
        framework_log("WARNING", f"Errore di validazione: {v.errors}", emoji="⚠️", data=processed_value)
        raise ValueError(f"⚠️ Errore di validazione: {v.errors} | data:{processed_value}")

    final_output = v.document
    return final_output

def transform(data_dict, mapper, values, input, output):
    """ Trasforma un set di costanti in un output mappato. """
    def find_matching_keys(mapper, target_dict):
        if not isinstance(mapper, dict) or not isinstance(target_dict, dict):
            return None
        target_keys = set(target_dict.keys())
        for key in mapper.keys():
            if key in target_keys:
                return key
        return None
    translated = {}

    if not isinstance(data_dict, dict):
        raise TypeError("Il primo argomento deve essere un dizionario.")

    if not isinstance(mapper, dict):
        raise TypeError("'mapper' deve essere un dizionario.")

    if not isinstance(values, dict):
        raise TypeError("'values' deve essere un dizionario.")
    
    if not isinstance(input, dict):
        raise TypeError("'input' deve essere un dizionario.")
    
    if not isinstance(output, dict):
        raise TypeError("'output' deve essere un dizionario.")

    key = find_matching_keys(mapper,output) or find_matching_keys(mapper,input)
    for k, v in mapper.items():
        n1 = get(data_dict, k)
        n2 = get(data_dict, v.get(key, None))
        
        if n1:
            output_key = v.get(key, None)
            value = n1
            translated |= put2(translated, output_key, value, output)
        if n2:
            output_key = k
            value = n2
            translated |= put2(translated, output_key, value, output)

    fieldsData = data_dict.keys()
    fieldsOutput = output.keys()

    for field in fieldsData:
        if field in fieldsOutput:
            value = get(data_dict, field)
            translated |= put2(translated, field, value, output)

    return translated

def _get_next_schema(schema, key):
    if isinstance(schema, dict):
        if 'schema' in schema:
            if schema.get('type') == 'list': return schema['schema']
            if isinstance(schema['schema'], dict): return schema['schema'].get(key)
        return schema.get(key)
    return None

def route(url: dict, new_part: str) -> str:
    """
    Updates the URL's path and/or adds query parameters based on the input string.
    """
    url = copy.deepcopy(url)
    protocol = url.get("protocol", "http")
    host = url.get("host", "localhost")
    port = url.get("port")
    path = url.get("path", [])
    query_params = url.get('query', {})
    fragment = url.get("fragment", "")

    parsed_new_part = urlparse(new_part)

    if parsed_new_part.path:
        path = [p for p in parsed_new_part.path.split('/') if p]

    if parsed_new_part.query:
        [query_params.setdefault(k, []).append(v) for k, v in (param.split('=', 1) for param in parsed_new_part.query.split('&') if '=' in param)]
        for key, value in query_params.items():
            pass
    
    query_parts = []
    query_string = ""
    for key, values in query_params.items():
        if values:  # prendi solo l'ultimo elemento
            query_parts.append(f"{key}={values[-1]}")
    query_string = "&".join(query_parts)

    base_url = ""
    if path:
        base_url += "/" + "/".join(path)

    if query_string:
        base_url += f"?{query_string}"
    
    if fragment:
        base_url += f"#{fragment}"

    return base_url

def get(data, path, default=None):
    if not path:
        return data
    
    # Partition del path per separare la prima chiave dal resto
    key, _, rest = path.partition(".")
    
    # Regex per catturare pattern del tipo: nome[attr=valore] o *[attr=valore]
    # Gestisce opzionalmente apici singoli o doppi attorno al valore
    filter_match = re.match(r"([^\[]+)\[([^=]+)=[\"']?([^\"']+)[\"']?\]", key)
    
    if filter_match:
        key_base, attr, expected = filter_match.groups()
        
        # Identifica la sorgente del filtro
        if key_base == "*":
            target = data if isinstance(data, (list, tuple)) else []
        else:
            target = data.get(key_base, []) if isinstance(data, (dict, Mapping)) else []
            
        # Filtra gli elementi: cast a stringa per confronto robusto
        filtered = [x for x in target if isinstance(x, dict) and str(x.get(attr)) == expected]
        
        # Ricorsione: applica il 'rest' su ogni elemento filtrato
        results = [get(item, rest, default) for item in filtered]
        
        # Ritorna il risultato (o None/default se la lista è vuota)
        return results if results else default

    # Gestione Wildcard pura
    if key == "*":
        if isinstance(data, (list, tuple)):
            return [get(x, rest, default) for x in data]
        return default
        
    # Navigazione standard (Dict, Mapping, List, Attribute)
    try:
        if isinstance(data, (dict, Mapping)):
            value = data.get(key, default)
        elif isinstance(data, (list, tuple)) and key.lstrip("-").isdigit():
            idx = int(key)
            value = data[idx] if 0 <= idx < len(data) else default
        else:
            value = getattr(data, key, default)
            
        return get(value, rest, default) if rest else value
    except (IndexError, TypeError, ValueError, KeyError):
        return default

def put(data, path, value):
    if not path:
        return value
    
    res = copy.deepcopy(data)
    key, _, rest = path.partition(".")
    
    # --- GESTIONE BULK / FILTRO CON REGEX ---
    # La regex cattura: key_base, attr, expected
    # Supporta: key[attr=valore], key[attr='valore'], key[attr="valore"]
    filter_match = re.match(r"([^\[]+)\[([^=]+)=[\"']?([^\"']+)[\"']?\]", key)
    
    if key == "*" or filter_match:
        if not isinstance(res, list):
            # Se la struttura non è una lista, non possiamo filtrare: restituiamo il dato originale
            return data
        
        if key == "*":
            return [put(item, rest, value) for item in res]
        
        # Estrazione dati dalla regex
        key_base, attr, expected = filter_match.groups()
        
        # Applicazione filtro: aggiorna solo gli elementi che corrispondono
        return [
            put(item, rest, value) if str(item.get(attr)) == expected else item 
            for item in res
        ]

    # --- IDENTIFICAZIONE CHIAVE ---
    is_idx = key.lstrip("-").isdigit()
    idx = int(key) if is_idx else key

    # --- PROTEZIONE ACCESSO A LISTA CON STRINGA ---
    if isinstance(res, list) and not is_idx:
        return data

    # --- LOOK-AHEAD: CREAZIONE DINAMICA ---
    # Creazione nodo se la chiave non esiste
    if isinstance(res, dict) and key not in res:
        next_key, _, _ = rest.partition(".")
        is_next_idx = next_key.lstrip("-").isdigit()
        res[key] = [] if is_next_idx else {}
    
    elif isinstance(res, list):
        if not is_idx or idx >= 999: return data
        if idx >= len(res):
            res.extend([None] * (idx - len(res) + 1))
            # Decidiamo se creare un dizionario o una lista per il nuovo slot
            next_key, _, _ = rest.partition(".")
            res[idx] = [] if next_key.lstrip("-").isdigit() else {}

    # --- ESECUZIONE PUT RICORSIVA ---
    if isinstance(res, list):
        if idx >= len(res): return data
        res[idx] = put(res[idx], rest, value)
    elif isinstance(res, dict):
        res[key] = put(res.get(key), rest, value)
    else:
        # Se res è un tipo primitivo che non può contenere chiavi
        return data
        
    return res