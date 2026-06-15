import framework.port.presentation as presentation
from framework.manager.loader import Loader

import re

class Manager:
    def __init__(self, presentations: list[presentation.Port], loader:Loader, **constants):
        self.presentations = presentations
        self.loader = loader
        #self.executor = constants.get('executor')

    async def start(self):
        loops = []
        for presentation in self.presentations:
            if hasattr(presentation, 'start'):
                res = await presentation.start()
                if res:
                    loops.append(res)
        return loops

    async def stop(self):
        for presentation in self.presentations:
            if hasattr(presentation, 'stop'):
                await presentation.stop()

    async def get_view(self,path):
        return await self.loader.resource(path)

    def _get_driver(self):
        return self.presentations[-1] if self.presentations else None

    def estrai_attributi_tag(self, tag_string: str):
        """
        Riceve una stringa del tag XML/DSL ed estrae tutti gli attributi in un dizionario.
        Gestisce sia virgolette singole che doppie.
        """
        # Questa regex cerca pattern tipo: chiave="valore" oppure chiave='valore'
        pattern = r'(\w+)=["\']([^"\']*)["\']'
        
        # Trova tutte le corrispondenze nella stringa
        matches = re.findall(pattern, tag_string)
        
        # Converte la lista di tuple (chiave, valore) in un dizionario
        return dict(matches)

    async def selector(self,**constants):
        driver = self._get_driver()
        return await driver.selector(**constants) if driver else None

    async def get_attribute(self,**constants):
        driver = self._get_driver()
        return await driver.get_attribute(constants.get('widget'),constants.get('field')) if driver else None

    async def builder(self,**constants):
        driver = self._get_driver()
        return await driver.builder(**constants) if driver else None
    
    async def navigate(self,**constants):
        driver = self._get_driver()
        return await driver.apply_route(**constants) if driver else None

    async def component(self,**constants):
        name = constants.get('name','')
        driver = self._get_driver()
        return driver.components[name] if driver else None
        
    async def rebuild(self,node_id,session_id,context):
        driver = self._get_driver()
        if driver and hasattr(driver, 'rebuild'):
            await driver.rebuild(node_id,session_id,context)