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
    run_module = asyncio.run(main(sys.argv))