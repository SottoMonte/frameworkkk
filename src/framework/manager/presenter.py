import framework.port.presentation as presentation
from framework.manager.loader import Loader

import re
import xml.etree.ElementTree as ET
from pathlib import Path

class Manager:
    def __init__(self, presentations: list[presentation.Port], loader:Loader, **constants):
        self.presentations = presentations
        self.loader = loader
        #self.executor = constants.get('executor')

    async def start(self, session):
        loops = []
        for presentation in self.presentations:
            if hasattr(presentation, 'start'):
                res = await presentation.start()
                if res:
                    loops.append(res)
        return loops

    async def stop(self , session):
        for presentation in self.presentations:
            if hasattr(presentation, 'stop'):
                await presentation.stop()

    async def get_view(self,path):
        return await self.loader.resource(path)

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

    async def get_attribute(self,**constants):
        driver = self._get_driver()
        return await driver.get_attribute(constants.get('widget'),constants.get('field')) if driver else None

    async def builder(self,**constants):
        driver = self._get_driver()
        return await driver.builder(**constants) if driver else None
    
    async def navigate(self,**constants):
        driver = self._get_driver()
        return await driver.apply_route(**constants) if driver else None

    async def component(self,**constants):
        name = constants.get('name','')
        driver = self._get_driver()
        return driver.components[name] if driver else None
        
    async def rebuild(self,node_id,session_id,context):
        driver = self._get_driver()
        if driver and hasattr(driver, 'rebuild'):
            await driver.rebuild(node_id,session_id,context)

    async def update_node(self, node_id, attrs=None, text=None, children=None):
        """Aggiorna un nodo XML salvato nel DOM in memoria, senza tocciare il file fisico."""
        driver = self._get_driver()
        if driver is None:
            raise RuntimeError("Nessun driver disponibile per aggiornare il DOM")

        dom = getattr(driver, "DOM", None)
        if not isinstance(dom, dict):
            raise TypeError("Il driver deve esporre un attributo DOM come dizionario")

        if node_id not in dom:
            raise KeyError(f"Nodo con id '{node_id}' non trovato nel DOM")

        xml_fragment = dom[node_id]
        if isinstance(xml_fragment, ET.Element):
            root = xml_fragment
        else:
            if isinstance(xml_fragment, bytes):
                xml_fragment = xml_fragment.decode("utf-8")
            root = ET.fromstring(f"<root>{xml_fragment}</root>")

        target = root.find(f".//*[@id='{node_id}']")
        if target is None:
            if root.attrib.get("id") == node_id:
                target = root
            else:
                raise KeyError(f"Nodo con id '{node_id}' non trovato nel DOM")

        if attrs:
            for key, value in attrs.items():
                if value is None:
                    target.attrib.pop(key, None)
                else:
                    target.attrib[key] = str(value)

        if text is not None:
            for child in list(target):
                target.remove(child)
            target.text = str(text)

        if children is not None:
            for child in list(target):
                target.remove(child)
            for child in children:
                if isinstance(child, ET.Element):
                    target.append(child)
                else:
                    target.text = str(child)

        dom[node_id] = ET.tostring(target, encoding="unicode")

        if hasattr(driver, "dom_update") and callable(getattr(driver, "dom_update")):
            await driver.dom_update(node_id, {"attrs": attrs or {}, "inner": [text] if text is not None else []})
        elif hasattr(driver, "apply_node_update") and callable(getattr(driver, "apply_node_update")):
            await driver.apply_node_update(node_id, attrs=attrs, text=text, children=children)

        return dom[node_id]