
class presenter():
    def __init__(self,**constants):
        self.presentations = constants.get('presentations', [])
        self.executor = constants.get('executor')

    async def start(self):
        for presentation in self.presentations:
            if hasattr(presentation, 'start'):
                await presentation.start()

    async def stop(self):
        for presentation in self.presentations:
            if hasattr(presentation, 'stop'):
                await presentation.stop()

    def _get_driver(self):
        return self.presentations[-1] if self.presentations else None

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