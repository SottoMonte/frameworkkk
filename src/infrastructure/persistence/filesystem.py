import sys
import os
import time
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import framework.port.persistence as persistence
import framework.service.flow as flow
from framework.manager.messenger import Manager as Messenger


class FileWatcherHandler(FileSystemEventHandler):
    def __init__(self, adapter, session, loop):
        self.adapter = adapter
        self.session = session
        self.loop = loop  
        self._last_modified_times = {}
        self._debounce_interval = 0.2

    def _trigger_event(self, event_type, event):
        if event.is_directory:
            return
            
        current_time = time.time()
        # Applichiamo il debounce principalmente sulle modifiche per evitare loop o eventi duplicati
        if event_type == "file_modified":
            if current_time - self._last_modified_times.get(event.src_path, 0) < self._debounce_interval:
                return
            self._last_modified_times[event.src_path] = current_time

        coro = self.adapter.handle_watcher_event(self.session, event_type, event.src_path)
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def on_modified(self, event):
        self._trigger_event("modified", event)

    def on_created(self, event):
        self._trigger_event("created", event)

    def on_deleted(self, event):
        self._trigger_event("deleted", event)

    def on_moved(self, event):
        # Per i file spostati potresti voler tracciare anche event.dest_path
        if event.is_directory:
            return
        coro = self.adapter.handle_watcher_event(self.session, "moved", event.src_path, event.dest_path)
        asyncio.run_coroutine_threadsafe(coro, self.loop)


class Adapter(persistence.Port):
    def __init__(self, messenger: Messenger, **constants):
        self.messenger = messenger
        self.config = constants
        self.name = constants.get('name')
        self.path = constants.get('path')
        self.watch = constants.get('watch', False)
        self.observer = None

    async def start(self, session=None):
        if self.watch:
            main_loop = asyncio.get_running_loop()
            self._start_watcher(session, main_loop)

    def _start_watcher(self, session, main_loop):
        print(f"👀 Avvio del watcher su '{self.path}'...")
        event_handler = FileWatcherHandler(adapter=self, session=session, loop=main_loop)
        self.observer = Observer()
        self.observer.schedule(event_handler, path=self.path, recursive=True)
        self.observer.start()
        print(f"🚀 Watcher attivo!")

    async def handle_watcher_event(self, session, event_type, filepath):
        await self.messenger.post(
            session,
            message=filepath,      
            domain=f"event.{event_type}"
        )
        

    def stop_watcher(self):
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join()
                print("👋 Watcher interrotto correttamente.")
            except Exception:
                pass

    def __del__(self):
        if self.observer and self.observer.is_alive():
            self.stop_watcher()

    @flow.result()
    async def request(self, **constants):
        filename = constants.get('filter', {}).get('eq', {}).get('filename')
        if filename:
            with open(filename, "a", encoding="utf-8") as file:
                file.write(str(constants) + "\n")
        return flow.success(None)

    # --- Operazioni CRUD standard di modello ---
    async def create(self, **constants): return await self.request(**{'method': 'POST'} | constants)
    async def delete(self, **constants): return await self.request(**{'method': 'DELETE'} | constants)
    async def update(self, **constants): return await self.request(**{'method': 'PUT'} | constants)
    async def read(self, **constants): return await self.request(**{'method': 'GET'} | constants)

    # --- Operazioni Infrastrutturali (View & Query) ---

    @flow.result()
    async def view(self, **constants):
        """
        Invocato da Manager.overview().
        Raccoglie ricorsivamente tutto il contenuto del file system e delega a query il filtraggio.
        """
        if not self.path or not os.path.exists(self.path):
            return flow.failure(f"La path '{self.path}' non esiste o non è valida.")

        all_items = []
        try:
            for root, dirs, files in os.walk(self.path):
                relative_root = os.path.relpath(root, self.path)
                if relative_root == ".":
                    relative_root = ""

                # Estrazione directory
                for d in dirs:
                    all_items.append({
                        "type": "directory",
                        "name": d,
                        "relative_path": os.path.join(relative_root, d),
                        "absolute_path": os.path.join(root, d)
                    })
                
                # Estrazione file
                for f in files:
                    all_items.append({
                        "type": "file",
                        "name": f,
                        "relative_path": os.path.join(relative_root, f),
                        "absolute_path": os.path.join(root, f)
                    })
            
            # 🌟 Passiamo la lista completa e i costanti originari (con i filtri) al metodo query
            return await self.query(dataset=all_items, **constants)
            
        except Exception as e:
            return flow.failure(f"Errore durante l'ispezione della path: {str(e)}")

    @flow.result()
    async def query(self, **constants):
        """
        Esegue la logica di filtraggio sul dataset passato da view.
        """
        dataset = constants.get('dataset')
        filters = constants.get('filter', {})

        # Fallback se query viene invocato direttamente senza il dataset di view
        if dataset is None:
            return await self.request(**{'method': 'GET'} | constants)

        filtered_items = dataset

        # Filtro sul tipo: es. filter={"type": {"eq": "file"}} o {"type": {"eq": "directory"}}
        type_filter = filters.get('type', {}).get('eq')
        if type_filter:
            filtered_items = [item for item in filtered_items if item['type'] == type_filter]

        # Puoi estendere qui altri filtri (es. estensione file, substring nel nome ecc.)
        name_filter = filters.get('name', {}).get('eq')
        if name_filter:
            filtered_items = [item for item in filtered_items if item['name'] == name_filter]

        return flow.success(filtered_items)