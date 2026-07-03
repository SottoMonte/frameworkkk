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
    def __init__(self, adapter, session, loop):  # 🌟 Riceve il loop principale
        self.adapter = adapter
        self.session = session
        self.loop = loop  
        self._last_modified_times = {}
        self._debounce_interval = 0.2

    def on_modified(self, event):
        if event.is_directory:
            return

        current_time = time.time()
        if current_time - self._last_modified_times.get(event.src_path, 0) < self._debounce_interval:
            return
        self._last_modified_times[event.src_path] = current_time

        # 🌟 Usiamo in modo sicuro il loop principale salvato nell'__init__
        coro = self.adapter.handle_watcher_event(self.session, event.src_path)
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
            # 🌟 Catturiamo il loop principale QUI, mentre siamo nel thread di asyncio
            main_loop = asyncio.get_running_loop()
            self._start_watcher(session, main_loop)

    def _start_watcher(self, session, main_loop):
        print(f"👀 Avvio del watcher su '{self.path}'...")
        
        # Passiamo il loop principale recuperato in precedenza
        event_handler = FileWatcherHandler(adapter=self, session=session, loop=main_loop)
        
        self.observer = Observer()
        self.observer.schedule(event_handler, path=self.path, recursive=True)
        self.observer.start()
        print(f"🚀 Watcher attivo!")

    async def handle_watcher_event(self, session, filepath):
        await self.messenger.post(
            session, 
            message=f"Il file {filepath} è stato modificato!", 
            domain="console:info"
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
        # Evita che errori di garbage collection blocchino la chiusura
        if self.observer and self.observer.is_alive():
            self.stop_watcher()

    # --- Gli altri metodi del framework rimangono invariati ---
    @flow.result()
    async def request(self, **constants):
        filename = constants.get('filter', {}).get('eq', {}).get('filename')
        if filename:
            with open(filename, "a", encoding="utf-8") as file:
                file.write(str(constants) + "\n")
        return flow.success(None)

    async def create(self, **constants): return await self.request(**{'method': 'POST'} | constants)
    async def delete(self, **constants): return await self.request(**{'method': 'DELETE'} | constants)
    async def read(self, **constants): return await self.request(**{'method': 'GET'} | constants)
    async def update(self, **constants): return await self.request(**{'method': 'PUT'} | constants)
    async def view(self, **constants): return await self.request(**{'method': 'GET'} | constants)
    async def query(self, **constants): return await self.request(**{'method': 'GET'} | constants)