import sys
import asyncio

import framework.port.message as message
import framework.service.flow as flow

from framework.manager.defender import Manager as Defender


'''async def shutdown(self):
        ...

    async def startup(self):
        ...'''

class Manager:

    def __init__(self, messages: list[message.Port], defender:Defender, **constants):
        self.defender = defender
        self.providers = messages

    @staticmethod
    def _split_domain(domain: str | None) -> tuple[str | None, str | None]:
        """
        Spezza 'controller:domain' in (controller, domain).
        Se non c'è ':' ritorna (None, domain) invariato.
        """
        if domain and ':' in domain:
            controller, domain = domain.split(':', 1)
            return controller, domain
        return None, domain

    def _matching_providers(self, controller: str | None) -> list:
        """
        Ritorna i provider che corrispondono al controller.
        Se controller è None, ritorna tutti i provider (nessun filtro).
        """
        if controller is None:
            return list(self.providers)
        return [
            p for p in self.providers
            if p.config.get('name') == controller or p.adapter == controller
        ]

    def route_provider(self,package):
        controller, domain = self._split_domain(package.get('domain'))
        matched = self._matching_providers(controller)

    @flow.result(inputs='messenger')
    async def post(self, session, **constants):
        message_text = constants.get('message')
        controller, domain = self._split_domain(constants.get('domain'))

        matched = self._matching_providers(controller)

        if controller and not matched:
            if controller in self.defender.controllers:
                await session.emit(controller, domain, message_text)
            # altrimenti: nessun provider adatto, nessuna azione (comportamento invariato)
            return

        for provider in matched:
            await provider.post(**constants | {'domain': domain})

    async def post2(self, session, **constants):
        #payload = constants.get('payload')
        message = constants.get('message')
        domain = constants.get('domain')
        controller = None
        if ':' in domain:
            controller = domain.split(':')[0]
            domain = domain.split(':')[1]

        
        for provider in self.providers:
            #print(controller,provider.adapter == controller, provider.config.get('name') == controller)
            #if controller == 'terminal':
            #    raise Exception(f"messenger.post: provider={provider} controller={controller}, domain={domain}, payload={payload} provider.config.get('name')={provider.config.get('name')}, provider.adapter={provider.adapter}")

            if controller:
                if  provider.config.get('name') == controller:
                    await provider.post(**constants|{'domain': domain})
                elif  provider.adapter == controller: 
                    await provider.post(**constants|{'domain': domain})
                elif controller in self.defender.controllers:
                    await session.emit(controller,domain,message)
                    #a = str(session.context)
                    #raise Exception(f"messenger.post: provider={provider} controller={controller}, domain={domain}, session.context={a}")
                    #await self.post(session,message=f"{controller}:{domain}"+a, domain="console:info")
                else: 
                    pass
                    #await self.post(session,message=f"Provider {provider} non è adatto per il dominio '{domain}' (controller '{controller}')", domain="console:warning")
            else:
                await provider.post(**constants|{'domain': domain})

    async def read(self, session, **constants):
        controller, domain = self._split_domain(constants.get('domain'))
        matched = self._matching_providers(controller)

        if controller and not matched:
            if controller in self.defender.controllers:
                # TODO: definire come leggere dal defender per questo controller,
                # analogamente a session.emit(...) usato in post
                return None
            return None

        tasks = [
            asyncio.create_task(provider.read(session,**constants | {'domain': domain}))
            for provider in matched
        ]

        if not tasks:
            return None

        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            result = done.pop().result()
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            return result
        except Exception as e:
            print(f"[Messenger] Errore nel loop di lettura: {e}")
            return None