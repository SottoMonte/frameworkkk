import sys
import framework.port.persistence as persistence
import framework.service.flow as flow
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os


class FileWatcherHandler(FileSystemEventHandler):
    def __init__(self, callback=None , target_file=None):
        self.target_file = target_file
        self.callback = callback

    
    def on_modified(self, event):
        print(f"FileWatcherHandler.on_modified: event.src_path={event.src_path}")
        if event.is_directory:
            return
        print(f"🔥 Il file {event.src_path} è stato modificato!")
        if self.callback:
            self.callback(event.src_path)


class Adapter(persistence.Port):

    def __init__(self, **constants):
        self.config = constants
        self.name = constants.get('name')
        self.path = constants.get('path')
        self.watch = constants.get('watch', False)
        self.observer = None
        print(f"📁 Adapter FileSystem inizializzato con path: {self.path}, watch: {self.watch}")
        if self.watch:
            self._start_watcher()

    def _start_watcher(self):
        event_handler = FileWatcherHandler(callback=self._on_file_changed)
        self.observer = Observer()
        self.observer.schedule(event_handler, path=self.path, recursive=True)
        self.observer.start()
        print(f"👀 Watcher avviato su '{self.path}' per il file '{self.name}'...")

    def _on_file_changed(self, filepath):
        # Questo viene chiamato dal thread del watcher, NON dall'event loop asyncio.
        with open("log_chiusura.txt", "a", encoding="utf-8") as f:
            f.write(f"Il programma è stato chiuso correttamente dal watcher.\n")
            f.write(f"File modificato: {filepath}\n")
        # Se ti serve triggerare codice async da qui, vedi nota sotto.sss
        '''asyncio.run_coroutine_threadsafe(
            self.request(filter={'eq': {'filename': filepath}}),
            self.loop
        )'''

    def stop_watcher(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("👋 Watcher interrotto.")

    def __del__(self):
        self.stop_watcher()

    @flow.result()
    async def request(self, **constants):
        filename = constants.get('filter', {}).get('eq', {}).get('filename')
        with open(filename, "a", encoding="utf-8") as file:
            file.write(str(constants) + "\n")
        print(constants)
        return flow.success(None)

    async def create(self, **constants):
        return await self.request(**{'method': 'POST'} | constants)

    async def delete(self, **constants):
        return await self.request(**{'method': 'DELETE'} | constants)

    async def read(self, **constants):
        return await self.request(**{'method': 'GET'} | constants)

    async def update(self, **constants):
        print('update:', constants)
        return await self.request(**{'method': 'PUT'} | constants)

    async def view(self, **constants):
        return await self.request(**{'method': 'GET'} | constants)

    async def query(self, **constants):
        return await self.request(**{'method': 'GET'} | constants)