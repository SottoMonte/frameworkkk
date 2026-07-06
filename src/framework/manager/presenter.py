import framework.port.presentation as presentation
from framework.manager.loader import Loader

import re
import xml.etree.ElementTree as ET

class Manager:
    def __init__(self, presentations: list[presentation.Port], loader:Loader, **constants):
        self.presentations = presentations
        self.loader = loader
        #self.executor = constants.get('executor')

    async def start(self, session):
        loops = []
        for presentation in self.presentations:
            if hasattr(presentation, 'start'):
                res = await presentation.start(session)
                if res:
                    loops.append(res)
        return loops

    async def stop(self , session):
        for presentation in self.presentations:
            if hasattr(presentation, 'stop'):
                await presentation.stop(session)

    async def get_view(self,path):
        return await self.loader.resource(path)

    async def get_attribute(self,**constants):
        driver = self._get_driver()
        return await driver.get_attribute(constants.get('widget'),constants.get('field')) if driver else None

    def _get_driver(self):
        return self.presentations[-1] if self.presentations else None

    def estrai_attributi_tag(self, tag_string: str):
        """
        Riceve una stringa del tag XML/DSL ed estrae tutti gli attributi in un dizionario.
        Gestisce sia virgolette singole che doppie.
        """
        # Questa regex cerca pattern tipo: chiave="valore" oppure chiave='valore'
        pattern = r'(\w+)=["\']([^"\']*)["\']'
        
        # Trova tutte le corrispondenze nella stringa
        matches = re.findall(pattern, tag_string)
        
        # Converte la lista di tuple (chiave, valore) in un dizionario
        return dict(matches)

    async def selector(self,**constants):
        driver = self._get_driver()
        return await driver.selector(**constants) if driver else None

    async def render(self, session, node_id, context=None):
        driver = self._get_driver()
        raise Exception(f"[render] driver={driver} node_id={node_id} context={context}")
        await driver.rebuild(node_id)
    
    async def navigate(self,**constants):
        driver = self._get_driver()
        return await driver.apply_route(**constants) if driver else None
        
    async def rebuild(self,node_id,session_id,context):
        driver = self._get_driver()
        if driver and hasattr(driver, 'rebuild'):
            await driver.rebuild(node_id,session_id,context)

    def split_text_and_children(self,inner=None):
        """Separa testo e figli mantenendo l'ordine dei contenuti."""
        text_parts = []
        children = []
        for item in inner or []:
            if isinstance(item, str):
                text_parts.append(item)
            else:
                children.append(item)
        return "".join(text_parts), children


    def apply_text_and_children(self, target, text=None, children=None):
        """Applica testo e figli a un elemento XML in modo centralizzato."""
        if text is None and children is None:
            return target

        for child in list(target):
            target.remove(child)

        if text is not None:
            target.text = str(text)
            return target

        if children is not None:
            for child in children:
                if isinstance(child, ET.Element):
                    target.append(child)
                else:
                    target.text = str(child)

        return target

    def estrai_da_nodo(self, nodo_padre, target_id):
        """
        Cerca un elemento per ID partendo da un nodo già esistente
        e lo restituisce come stringa XML.
        """
        # Cerchiamo il sotto-nodo partendo dal nodo_padre
        elemento = nodo_padre.find(f".//*[@id='{target_id}']")
        
        if elemento is not None:
            # Serializziamo il nodo trovato
            return ET.tostring(elemento, encoding='unicode', method='xml').strip()
        
        return None

    def estrai_da_xml_string(self, xml_string, target_id):
        if not xml_string:
            return None

        try:
            # Usiamo 'html.parser' che è SEMPRE presente in Python.
            # È meno schizzinoso di 'xml' e non richiede lxml.
            soup = BeautifulSoup(xml_string, 'html.parser')
            
            # Cerchiamo l'elemento con l'id specifico
            elemento = soup.find(attrs={"id": target_id})
            
            if elemento:
                # Serializziamo il risultato
                return str(elemento).strip()
                
        except Exception as e:
            print(f"Errore durante l'estrazione: {e}")
        
        return None