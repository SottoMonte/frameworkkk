import re
from urllib.parse import quote
from jinja2 import Environment, meta



class repository:
    def __init__(self, **constants):
        self.location = constants.get('location', {})
        self.actions = constants.get('actions', {})
        self.schema = constants.get('model')

    def get_requirements(self, template_str):
        """Estrae i requisiti (variabili globali) da un template Jinja2."""
        try:
            if not template_str or not isinstance(template_str, str) or '{' not in template_str:
                return []
            return list(meta.find_undeclared_variables(jinja.parse(template_str)))
        except Exception:
            return re.findall(r'\{(\w+)\}', template_str)

    def select(self, templates, data):
        """
        Sceglie il miglior template dalla lista in base ai dati forniti.
        Ritorna il template migliore o None.
        """
        best_t, max_score = None, -1
        
        for t in (templates if isinstance(templates, list) else [templates]):
            reqs = self.get_requirements(t)
            if not reqs:
                score = 0.1
            else:
                if all(scheme.get(data, r) is not None for r in reqs):
                    score = len(reqs) + (0.5 if '{%' in t else 0)
                else:
                    score = -1
            
            if score > max_score:
                max_score, best_t = score, t
                
        return best_t if max_score >= 0 else None

    async def results(self, transaction, profile):
        """Hook opzionale per post-processing."""
        return transaction

    async def parameters(self, **inputs):
        """Prepara i parametri della rotta risolvendo il template tramite Scheme."""
        
        operation = inputs.get('operation')
        profile = inputs.get('provider')
        action = self.actions.get(operation, {})
        
        # 1. Definizione Payload e Logica
        payload_fn = action.get('payload')
        payload = payload_fn(**inputs.get('payload', {})) if callable(payload_fn) else inputs.get('payload', {})
        
        logic_fn = action.get('logic')
        process = logic_fn(**inputs) if callable(logic_fn) else inputs
        
        # 2. Selezione dinamica del Template
        combined = {**inputs, **payload, **process}
        templates = self.location.get(profile, [])
        template = self.select(templates, combined)
        
        if not template:
            raise ValueError(f"Nessun template compatibile trovato per {profile}. Dati: {list(combined.keys())}")

        # 3. Formattazione e Encoding
        path = await scheme.format(template, **combined)
        
        if '?' in path:
            base, query = path.split('?', 1)
            path = f"{base}?{quote(query, safe='=&%')}"
        else:
            path = quote(path)
            
        return process | {
            'location': path, 
            'provider': profile, 
            'payload': payload, 
            'filter': inputs.get('filter', {})
        }