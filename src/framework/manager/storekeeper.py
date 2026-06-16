import asyncio
import importlib

import framework.port.persistence as persistence
import framework.service.flow as flow
from framework.service.factory import Repository

from framework.manager.messenger import Manager as Messenger
from framework.manager.orchestrator import Manager as Orchestrator
from framework.manager.defender import Manager as Defender

class Manager:

    def __init__(self,providers: list[persistence.Port], defender: Defender, orchestrator:Orchestrator, messenger: Messenger,**constants):
        self.orchestrator = orchestrator
        self.defender = defender
        self.persistences = providers
        self.repositories = {}
        self.maked = {}
        self.messenger = messenger

    async def start(self):
        '''for repository in self.repositories:
            self.maked[repository] = Repository(**self.repositories[repository])'''
        await self.messenger.post(message="Storekeeper avviato.", domain="console:info")

    async def stop(self):
        await self.messenger.post(message="Storekeeper arrestato.", domain="console:info")

    #@flow.result(inputs=("session",))
    async def preparation(self, session, storekeeper):
        repository_name = storekeeper.get('repository')
        if repository_name not in self.maked:
            path = f'src/application/repository/{repository_name}.dsl'
            code = await self.defender.loader.resource(path)
            await self.defender.interpreter.load_file(path, code)
            async with await self.defender.session_create() as session:
                 self.repositories[repository_name] = await session.run(name)
            #self.repositories[repository_name] = await self.defender.interpreter.run_once(path,code)
            self.maked[repository_name] = Repository(**self.repositories[repository_name]['repository'])
        
        repository = self.maked.get(repository_name)
        operations = []
        #print(repo_data)
        if repository:
            #print(repository.location)
            #print("##############",self.persistences)
            for provider in self.persistences:
                #print(provider)
                profile = provider.config.get('name')
                #print(profile)
                try:
                    
                    if not profile:
                        #language.framework_log("WARNING", f"Provider {provider} non ha un profilo configurato.", emoji="⚠️")
                        print(f"Provider {provider} non ha un profilo configurato.")
                        continue
                    #print("okkkkkkkkkkkkkkkk",repository)
                    if profile in [x.lower() for x in repository.location.keys()]:
                        try:
                            operation = storekeeper.get('operation')
                            task_args = await repository.parameters(**storekeeper|{'provider':profile})
                        except Exception as e:
                            #language.framework_log("ERROR", f"Errore durante l'ottenimento dei parametri per {profile}: {e}", emoji="❌")
                            print(f"Errore durante l'ottenimento dei parametri per {profile}: {e}")
                            continue

                        # Controllo che il metodo esista nel provider
                        method = getattr(provider, operation, None)
                        if not callable(method):
                            #language.framework_log("WARNING", f"Il metodo '{operation}' non è disponibile per il provider {profile}.", emoji="🚫")
                            print(f"Il metodo '{operation}' non è disponibile per il provider {profile}.")
                            continue

                        task = asyncio.create_task(method(**task_args), name=profile)
                        task.parameters = task_args
                        operations.append(task)
                    else:
                        #language.framework_log("DEBUG", f"Provider {provider} non ha un profilo trovato.", emoji="🔍")
                        print(f"Provider {provider} non ha un profilo trovato.")
                except Exception as e:
                    #language.framework_log("ERROR", f"Errore imprevisto durante la preparazione per il provider {provider}: {e}", emoji="🤯")
                    return flow.error(f"Errore imprevisto durante la preparazione per il provider {provider}: {e}")
            return flow.success((repository, operations))
        else:
            return flow.error(f"Repository '{repository}' non trovato o dati non disponibili.")
    
    # overview/view/get
    async def overview(self, session, **constants):
        #print("#####OVERVIEW#####",session,constants)
        resultato = await self.preparation(session,storekeeper=constants)
        repository,operations = flow.output(resultato)
        return await self.executor.first_completed(operations=operations,success=repository.results)

    # gather/read/get
    async def gather(self, session, storekeeper,**constants):
        state = await self.preparation(**constants|{'operation':'read'})
        repository,operations = flow.output(state)
        return await self.executor.first_completed(operations=operations,success=repository.results)
    
    # store/create/put
    @flow.result(inputs='storekeeper')
    async def store(self, session, **constants):

        state = await self.preparation(session,constants|{'operation':'create'})
        repository,operations = flow.output(state)
        #print(repository,operations)
        return await self.orchestrator.first_completed(operations=operations,success=repository.results)
        
    
    # remove/delete/delete
    async def remove(self, session, **constants):
        repository,operations = await self.preparation(constants|{'operation':'delete'})
        return await self.orchestrator.first_completed(operations=operations,success=repository.results)
    
    # change/update/patch
    async def change(self, session, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'update'})
        return await self.executor.first_completed(operations=operations,success=repository.results)