import sys
import os
import asyncio

async def main(argv=sys.argv):
    cwd = os.getcwd()
    sys.path.insert(1, cwd+'/src')
    import framework.manager.loader as loader
    
    loader_instance = loader.loader()
    return await loader_instance.bootstrap(argv)

if __name__ == "__main__":
    asyncio.run(main(sys.argv))