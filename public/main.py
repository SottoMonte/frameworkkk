import sys
import os
import asyncio

# Setup del path per trovare i moduli sotto 'src'
cwd = os.getcwd()
sys.path.insert(1, cwd + '/src')

from framework.manager.loader import Loader

async def main():
    loader_instance = Loader()
    
    # Il bootstrap ora chiede SOLO il file di configurazione dell'utente.
    # Tutto il resto viene risolto internamente al framework!
    app = await loader_instance.bootstrap("pyproject.toml")
    
    try:
        await app.start()
    except Exception as e:
        print(f"[!] Errore critico: {e}")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())