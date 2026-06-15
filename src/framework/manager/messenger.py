import sys
import asyncio

import framework.port.message as message
import framework.service.flow as flow

from framework.manager.defender import Manager as Defender

class Manager:

    def __init__(self, messages: list[message.Port], defender:Defender, **constants):
        self.defender = defender
        self.providers = messages

    @flow.result(inputs='messenger')
    async def post(self, session, **constants):
        
        payload = constants.get('payload')
        domain = constants.get('domain')
        controller = None
        if ':' in domain:
            controller = domain.split(':')[0]
            domain = domain.split(':')[1]

        for provider in self.providers:
            #print(controller,provider.adapter == controller, provider.config.get('name') == controller)
            if controller:
                if  provider.config.get('name') == controller:
                    await provider.post(**constants|{'domain': domain})
                elif  provider.adapter == controller: 
                    await provider.post(**constants|{'domain': domain})
                elif controller in self.defender.controllers:
                    exit(1)
                else: 
                    await self.post(message=f"Provider {provider} non è adatto per il dominio '{domain}' (controller '{controller}')", domain="console:warning")
            else:
                await provider.post(**constants|{'domain': domain})

    async def read(self, **constants):
        prohibited = constants['prohibited'] if 'prohibited' in constants else []
        allowed = constants['allowed'] if 'allowed' in constants else ['FAST']
        operations = []
        
        for provider in self.providers:
            profile = provider.config['profile'].upper()
            domain_provider = provider.config.get('domain','*').split(',')
            domain_message = constants.get('domain',[])
            task = asyncio.create_task(provider.read(location=profile,**constants))
            operations.append(task)
        
        return await self.executor.first_completed(operations=operations)
        '''finished, unfinished = await asyncio.wait(operations, return_when=asyncio.FIRST_COMPLETED)
        for operation in finished:
            return operation.result()
        #return finished[0].result()'''
        '''while operations:
            
            finished, unfinished = await asyncio.wait(operations, return_when=asyncio.FIRST_COMPLETED)
            
            
            for operation in finished:
                transaction = operation.result()
                if transaction['state']:
                    result = transaction['result']

                    for task in unfinished:
                        task.cancel()
                    if unfinished:
                        await asyncio.wait(unfinished)
                    
                    return result
                else:
                    if len(operations) == 1:
                        return transaction

            operations = unfinished'''