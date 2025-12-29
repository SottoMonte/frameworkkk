import asyncio
import redis.asyncio as r
import framework.port.message as message
import framework.service.flow as flow
import datetime
from ast import literal_eval
import importlib
import json

imports = {
    "framework": "framework/service/language.py",
    "flow": "framework/service/flow.py"
}

class adapter(message.port):

    def __init__(self,**constants):
        self.config = constants['config'] 
        self.connection = self.loader()
        self.processable = dict()

    def loader(self,*managers,**constants):
        return r.from_url(f"redis://{self.config['host']}:{self.config['port']}")

    @flow.asynchronous(args=('policy','name','value','identifier'),ports=('storekeeper',))
    async def post(self,storekeeper,**constants):
        payload = constants['value'] if 'value' in constants else ''
        domain = [self.app+'.'+constants['name']] if 'name' in constants else [self.app]
        identifier = constants['identifier'] if 'identifier' in constants else ''
        await self.signal(keys=domain,value=str(payload),identifier=identifier,name=constants['name'])

    @flow.asynchronous(ports=('storekeeper',))
    async def get(self,storekeeper,**constants):
        identifier = constants['identifier']
        max = 0
        while max < 10:
            await asyncio.sleep(0.5)
            output = await storekeeper.get(model='transaction',identifier=identifier)
            if output != None and output['state']:
                await storekeeper.pull(model='transaction',identifier=identifier)
                return output
            max += 1
        return storekeeper.builder('transaction',{'identifier':identifier,'state':False})
        

    async def signal(self,**constants):
        for key in constants['keys']:
            pp = constants['value']
            await self.connection.xadd(self.app,{'identifier':constants['identifier'],'payload':pp,'domain':key,'action':constants['name'],'time':str(datetime.datetime.now())})
        
    async def can(self,**constants):
        name = constants['name']
        try:
            model = importlib.import_module(f"application.plug.action.{name}", package=None)
            action = getattr(model,name)
            self.processable[name] = action
            return True
        except ImportError:return False

    @flow.asynchronous(ports=('storekeeper','messenger'))
    async def react(self, storekeeper,messenger, **constants):
        while True:
            await asyncio.sleep(1.1)
            message = await self.connection.xread(count=1, streams={constants['domain']:0} )
            
            if len(message) != 0:
                id = message[0][1][0][0]
                payload = message[0][1][0][1]
                
                str_dict = {k.decode('utf-8'): v.decode('utf-8') for k, v in payload.items()}
                a = storekeeper.builder('event',str_dict)
                key = a['domain'].split('.')
                a['payload'] = literal_eval(a['payload'])
                name = key[len(key)-1]
                if name in self.processable:
                    
                    await self.connection.xdel(constants['domain'],id)
                    response = await self.processable[name](**a)
                    await messenger.post(name="log",value=f"Action start {name}")
                    if 'identifier' in a and  '' != a['identifier']:
                        await storekeeper.put(model='transaction',identifier=a['identifier'],value=response)