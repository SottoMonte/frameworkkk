import sys
import framework.port.persistence as persistence
import framework.service.flow as flow

class Adapter(persistence.Port):
    
    def __init__(self, **constants):
        self.config = constants

    @flow.result()
    async def request(self, **constants):
        '''print('request:',constants)
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
        
        return await backend(method,url,headers,payload)'''
        print(constants)
        return flow.success(None)
        
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