import sys
import os
import asyncio

async def main(argv=sys.argv):
    cwd = os.getcwd()
    sys.path.insert(1, cwd+'/src')
    import framework.manager.loader as loader
    
    loader_instance = loader.loader(argv=argv)
    return await loader_instance.bootstrap()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    run_module = loop.run_until_complete(main(sys.argv))
    loop.run_forever()