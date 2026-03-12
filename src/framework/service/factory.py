import re
import framework.service.scheme as scheme
import framework.service.flow as flow

class repository:
    def __init__(self, **constants):
        self.location = constants.get('location', {})
        self.mapper = constants.get('mapper', {})
        self.values = constants.get('values', {})
        self.actions = constants.get('actions', {})
        self.schema = constants.get('model')

    def _get_placeholders(self, template):
        return re.findall(r'\{\{\s*([\w\.]+)\s*\}\}', template)

    def can_format(self, template, data):
        placeholders = self._get_placeholders(template)
        # Verifica se tutti i placeholder sono risolvibili (valore non None)
        results = [scheme.get(data, key) is not None for key in placeholders]
        return all(results), len(placeholders)

    def do_format(self, template, data):
        try:
            return template.format_map(data)
        except KeyError:
            return template

    def find_best_template(self, templates, data):
        # Trova il template con il maggior numero di placeholder risolvibili
        valid = [
            (t, count) for t, count in 
            [(t, self.can_format(t, data)[1]) for t in templates] 
            if self.can_format(t, data)[0]
        ]
        return max(valid, key=lambda x: x[1])[0] if valid else None

    async def results(self, **data):
        # Normalizza la struttura della transazione filtrando solo i dizionari
        transaction = data.get('transaction', {})
        results = transaction.get('result', [])
        
        if not isinstance(results, list):
            raise ValueError("Il campo 'result' deve essere una lista.")
            
        transaction['result'] = [item for item in results if isinstance(item, dict)]
        return transaction

    @flow.action()
    async def parameters(self, **inputs):
        # 1. Recupera l'action (payload + logica)
        ops = inputs.get('operation')
        profile = inputs.get('provider')
        action = self.actions.get(ops, {})
        
        payload = action.get('payload')
        payload = payload(**inputs.get('payload', {})) if callable(payload) else inputs.get('payload', {})
        process = action.get('logic')
        process = process(**inputs) if callable(process) else inputs
        
        # 2. Trasformazione dati via self.values
        processed_values = {}
        for key, transformer in self.values.items():
            if key in inputs:
                #processed_values[key] = await transformer.get('MODEL', lambda x: x)(inputs[key])
                pass
        
        # 3. Risoluzione template
        combined = {**inputs, **payload, **processed_values}
        #print(combined)
        templates = self.location.get(profile, [])
        #print(templates)
        template = self.find_best_template(templates, combined)
        #print(template)
        
        if not template:
            raise ValueError(f"Nessun template valido per: {profile}")

        # 4. Formattazione finale del percorso
        path = await scheme.format(template, **combined)
        
        return process | {'location': path, 'provider': profile, 'payload': payload, 'filter': inputs.get('filter', {})}