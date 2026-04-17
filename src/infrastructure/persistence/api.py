import sys
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs


def add_query_params(url, params):
    # Parsifica l'URL nei suoi componenti
    url_parts = urlparse(url)
    
    # Converte i parametri esistenti e i nuovi in un dizionario
    query_params = parse_qs(url_parts.query)
    query_params.update(params)
    
    # Codifica nuovamente i parametri come stringa
    new_query = urlencode(query_params, doseq=True)
    
    # Ricostruisce l'URL con i nuovi parametri
    new_url = urlunparse(url_parts._replace(query=new_query))
    return new_url

modules = {'flow': 'framework.service.flow',}

if sys.platform == 'emscripten':
    import pyodide
    import json

    async def backend(method,url,headers,payload):
        match method:
            case 'GET':
                response = await pyodide.http.pyfetch(url, method=method, headers=headers)
            case 'DELETE':
                response = await pyodide.http.pyfetch(url, method=method, headers=headers)
            case _:
                if type(payload) == dict:
                    payload = json.dumps(payload)
                else:
                    payload = json.dumps({})
                response = await pyodide.http.pyfetch(url, method=method, headers=headers,body=payload)
        if response.status in [200, 201]:
            data = await response.json()
            print(data)
            return {"state": True, "result": data}
        else:
            return {"state": False, "result":[],"remark": f"Request failed with status {response.status}"}
    '''async def backend(method, url, headers, payload=None):
        method_upper = method.upper()

        if method_upper in ['GET', 'DELETE']:
            response = await pyodide.http.pyfetch(url, method=method_upper, headers=headers)
        else:
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            else:
                payload = json.dumps({})
            response = await pyodide.http.pyfetch(url, method=method_upper, headers=headers, body=payload)

        if response.status in [200, 201, 204]:
            try:
                data = await response.json()
            except Exception:
                data = {}
            return {"state": True, "result": data}
        else:
            return {
                "state": False,
                "result": [],
                "remark": f"Request failed with status {response.status}"
            }'''
                
else:
    import aiohttp
    import json

    @flow.result()
    async def backend(method, url, headers, payload):
        async with aiohttp.ClientSession() as session:
            async with session.request(method=method, url=url, headers=headers, json=payload) as response:
                if response.status in [200, 201]:
                    # Controlliamo se il server dichiara di inviare JSON
                    if "application/json" in response.content_type:
                        data = await response.json()
                        return flow.success(data)
                    else:
                        # Se non è JSON, leggiamo come testo per capire cos'è
                        content = await response.text()
                        return flow.success(content)
                else:
                    return flow.error(f"Request failed with status {response.status}")

class adapter(persistence.port):
    
    def __init__(self, **constants):
        #print(constants,"########################")
        self.name = constants.get('provider')
        self.api_url = constants.get('url')
        self.token = constants.get('token') or constants.get('key')
        self.authorization = constants.get('authorization', 'Bearer ')
        self.accept = constants.get('accept', 'application/vnd.github+json')

    @flow.result(safe_kwargs=True)
    async def request(self, **constants):
        print('request:',constants)
        headers = {
            "Authorization": f"{self.authorization} {self.token}",
            "Accept": self.accept,
        }
        location = constants.get('location','').replace('//','/')
        method = constants.get('method','')
        payload = constants.get('payload',{})
        url = f"{self.api_url}{location}" if location else self.api_url
        print('url:',url)
        print('location:',location)
        #if payload and method == 'GET':
        #    url += '?' + urlencode(payload)
        
        return await backend(method,url,headers,payload)
        
    async def create(self, **constants):
        return await self.request(**{'method':'POST'}|constants)

    async def delete(self, **constants):
        return await self.request(**{'method':'DELETE'}|constants)

    async def read(self, **constants):
        return await self.request(**{'method':'GET'}|constants)

    async def update(self, **constants):
        print('update:',constants)
        return await self.request(**{'method':'PUT'}|constants)

    async def view(self,**constants):
        return await self.request(**{'method':'GET'}|constants)
    
    async def query(self,**constants):
        return await self.request(**{'method':'GET'}|constants)