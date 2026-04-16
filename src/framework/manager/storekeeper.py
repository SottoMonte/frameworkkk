import asyncio
import importlib

class Storekeeper():

    def __init__(self,**constants):
        self.executor = constants['executor']
        self.persistences = constants['persistences']
        self.repositories = constants['repositories']
        self.maked = {}

    async def start(self):
        print("###############################")
        for repository in self.repositories:
            self.maked[repository] = factory.repository(**self.repositories[repository])

        print("###############################",self.maked)

    @flow.result(inputs=("session",))
    async def preparation(self, session, storekeeper):
        repository_name = storekeeper.get('repository')
        repository = self.maked.get(repository_name)
        operations = []
        #print(repo_data)
        if repository:
            #print(repository.location)
            #print("##############",self.persistences)
            for provider in self.persistences:
                profile = provider.name.upper()
                print(profile)
                try:
                    
                    if not profile:
                        #language.framework_log("WARNING", f"Provider {provider} non ha un profilo configurato.", emoji="⚠️")
                        print(f"Provider {provider} non ha un profilo configurato.")
                        continue

                    if profile in repository.location:
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
                    print(e)
            return flow.success((repository, operations))
        else:
            print(f"[!] Repository '{repository}' non trovato o dati non disponibili.")

        return flow.success(storekeeper)
    
    # overview/view/get
    async def overview(self, session, **constants):
        #print("#####OVERVIEW#####",session,constants)
        resultato = await self.preparation(session,storekeeper=constants)
        repository,operations = resultato.get('outputs')
        return await self.executor.first_completed(operations=operations,success=repository.results)

    # gather/read/get
    async def gather(self, session, storekeeper,**constants):
        repository,operations = await self.preparation(**constants|{'operation':'read'})
        return await self.executor.first_completed(operations=operations,success=repository.results)
    
    # store/create/put
    async def store(self, session, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'create'})
        return await self.executor.first_completed(operations=operations,success=repository.results)
    
    # remove/delete/delete
    async def remove(self, session, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'delete'})
        return await self.executor.first_completed(operations=operations,success=repository.results)
    
    # change/update/patch
    async def change(self, session, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'update'})
        return await self.executor.first_completed(operations=operations,success=repository.results)