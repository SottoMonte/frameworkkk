import sys
import framework.port.persistence as persistence
import framework.service.flow as flow
from framework.manager.messenger import Manager as Messenger


from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import asyncio


class FileWatcherHandler(FileSystemEventHandler):
    def __init__(self, callback=None , session=None, target_file=None):
        self.target_file = target_file
        self.callback = callback
        self.session = session

    def on_modified(self, event):
        exit(1)
        print(f"FileWatcherHandler.on_modified: event.src_path={event.src_path}")
        if event.is_directory:
            return
            
        if self.callback:
            # Creiamo la coroutine
            coro = self.callback.post(
                self.session, 
                message=f"Il file {event.src_path} è stato modificato!", 
                domain="log:info"
            )
            
            # Recuperiamo il loop corrente (o passalo nell'__init__ se necessario)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # Se non c'è un loop nel thread corrente, usa quello principale se il framework lo espone
                # Nota: Assicurati che il framework non richieda un loop specifico
                loop = asyncio.get_running_loop()

            # Spediamo la coroutine in modo sicuro all'event loop asincrono
            exit(1)
            asyncio.run_coroutine_threadsafe(coro, loop)

    '''def on_modified(self, event):
        print(f"FileWatcherHandler.on_modified: event.src_path={event.src_path}")
        if event.is_directory:
            return
        if self.callback:
            #self.callback(event.src_path)
            self.callback.post(self.session, message=f"Il file {event.src_path} è stato modificato!", domain="console:info")
    
    def on_created(self, event):
        if event.is_directory:
            print(f"📁 Nuova directory creata: {event.src_path}")
        else:
            print(f"✨ Nuovo file creato: {event.src_path}")
        # Se serve, qui puoi invocare la callback
        if self.callback:
            self.callback(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            print(f"🗑️ Directory eliminata: {event.src_path}")
        else:
            print(f"🗑️ File eliminato: {event.src_path}")
        # Se serve, qui puoi invocare la callback
        if self.callback:
            self.callback(event.src_path)
            
    def on_moved(self, event):
        # Opzionale: intercetta anche quando file o cartelle vengono rinominati/spostati
        tipo = "Directory" if event.is_directory else "File"
        print(f"🔀 {tipo} spostato/rinominato da {event.src_path} a {event.dest_path}")'''


class Adapter(persistence.Port):

    def __init__(self, messenger: Messenger, **constants):
        self.messenger = messenger
        self.config = constants
        self.name = constants.get('name')
        self.path = constants.get('path')
        self.watch = constants.get('watch', False)
        self.observer = None

    async def start(self, session):
        print(f"👀 Watcher avviato su '{self.path}' per il file '{self.name}'...")
        if self.watch == True:
            self._start_watcher(session)

    def _start_watcher(self , session):
        print(f"👀 Avvio del watcher su '{self.path}' per il file '{self.name}'...")
        #event_handler = FileWatcherHandler(callback=self._on_file_changed)
        event_handler = FileWatcherHandler(callback=self.messenger, session=session)
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