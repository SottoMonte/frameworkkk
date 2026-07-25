import sys
import os
import asyncio
import argparse # Importa la libreria necessaria

# Setup del path
cwd = os.getcwd()
sys.path.insert(1, cwd + '/src')

from framework.manager.loader import Loader

async def main(config):
    loader_instance = Loader()
    
    # Usa il parametro passato dal terminale
    app = await loader_instance.bootstrap(config)
    
    try:
        await app.startup()
    except Exception as e:
        print(f"[!] Errore critico: {e}")
    finally:
        await app.shutdown()

if __name__ == "__main__":
    # Configurazione dell'argparse
    parser = argparse.ArgumentParser(description="Avvia il framework con una configurazione specifica.")
    
    parser.add_argument(
        "--config", 
        type=str, 
        default="pyproject.toml", 
        help="Percorso del file di configurazione (default: pyproject.toml)"
    )

    parser.add_argument("--debug", action="store_true", help="Abilita la modalità debug")
    parser.add_argument("--dev", action="store_true", help="Abilita la modalità dev")

    args = parser.parse_args()
    args_dict = vars(args)
    
    # Esecuzione con il parametro passato
    asyncio.run(main(args_dict))