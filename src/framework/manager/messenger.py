import sys
import asyncio

class messenger():

    def __init__(self,**constants):
        self.executor = constants.get('executor')
        self.providers = constants.get('messages', [])

    async def post(self, **constants):
        session_id = constants['session']
        payload = constants.get('payload')
        domain = constants.get('domain')
        node_id = constants.get('node')  # opzionale: id del nodo DOM da aggiornare

        file_path = None
        event_name = None

        if ':' in domain:
            controller = domain.split(':')[0]
            event_name = domain.split(':')[1]
            file_path = f"src/application/controller/{controller}.dsl"

        # 1. Aggiorna lo stato nella sessione
        if file_path and event_name:
            #print(f"[messenger] update_state: {event_name} = {payload} (session: {session_id})")
            #self.executor.interpreter.runner.update_state(session_id, file_path, event_name, payload)
            self.executor.interpreter.runner.emit(session_id, file_path, event_name, payload)

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