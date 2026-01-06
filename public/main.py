import sys
import os
import asyncio

async def main():
    cwd = os.getcwd()
    sys.path.insert(1, cwd+'/src')
    import framework.manager.loader as loader
    
    loader_instance = loader.loader()
    load_filtered = await loader_instance.resource(path="framework/service/load.py")
    load_filtered = load_filtered.get('data')

    # Load language module first (needed by other modules)
    await load_filtered.resource(path="framework/service/language.py")
    
    # Load run module
    run_result = await load_filtered.resource(path="framework/service/run.py")
    return run_result.get('data') if isinstance(run_result, dict) else run_result

if __name__ == "__main__":
    run_module = asyncio.run(main())
    run_module.application(args=sys.argv)