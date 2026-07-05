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

    def _get_dom(self, driver):
        dom = getattr(driver, "DOM", None)
        if not isinstance(dom, dict):
            raise TypeError("Il driver deve esporre un attributo DOM come dizionario")
        return dom

    def _resolve_target(self, dom, node_id):
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
        return root, target

    def _build_element(self, tag, attrs=None, text=None, children=None, *, node_id=None):
        element = ET.Element(tag)
        if node_id:
            element.set("id", node_id)
        if attrs:
            for key, value in attrs.items():
                if value is not None:
                    element.set(key, str(value))
        if text is not None:
            element.text = str(text)
        if children:
            for child in children:
                if isinstance(child, ET.Element):
                    element.append(child)
                else:
                    element.text = str(child)
        return element

    def _apply_attrs(self, target, attrs=None):
        if attrs:
            for key, value in attrs.items():
                if value is None:
                    target.attrib.pop(key, None)
                else:
                    target.attrib[key] = str(value)
        return target

    async def _notify_driver(self, driver, node_id, attrs=None, text=None, children=None):
        if hasattr(driver, "dom_update") and callable(getattr(driver, "dom_update")):
            await driver.dom_update(node_id, {"attrs": attrs or {}, "inner": [text] if text is not None else []})
        elif hasattr(driver, "apply_node_update") and callable(getattr(driver, "apply_node_update")):
            await driver.apply_node_update(node_id, attrs=attrs, text=text, children=children)

    async def _apply_to_dom(self, driver, node_id, attrs=None, text=None, children=None, *, action: str = "update", tag=None, new_id=None):
        dom = self._get_dom(driver)
        if action == "remove":
            if node_id not in dom:
                raise KeyError(f"Nodo con id '{node_id}' non trovato nel DOM")
            dom.pop(node_id, None)
            await self._notify_driver(driver, node_id, attrs=None, text=None, children=None)
            return None

        if action == "create":
            if not tag:
                raise ValueError("tag è obbligatorio per create")
            element = self._build_element(tag, attrs=attrs, text=text, children=children, node_id=new_id)
            node_key = new_id or element.get("id") or f"node_{len(dom)}"
            dom[node_key] = ET.tostring(element, encoding="unicode")
            await self._notify_driver(driver, node_key, attrs=attrs, text=text, children=children)
            return dom[node_key]

        if action == "replace":
            if not tag:
                raise ValueError("tag è obbligatorio per replace")
            root, target = self._resolve_target(dom, node_id)
            parent = target.getparent() if hasattr(target, "getparent") else None
            replacement = self._build_element(tag, attrs=attrs, text=text, children=children, node_id=new_id or target.attrib.get("id"))
            if parent is not None:
                index = list(parent).index(target)
                parent.insert(index, replacement)
            else:
                root = replacement
            dom[node_id] = ET.tostring(replacement, encoding="unicode")
            await self._notify_driver(driver, new_id or node_id, attrs=attrs, text=text, children=children)
            return dom[node_id]

        if action != "update":
            raise ValueError(f"Azione DOM non supportata: {action}")

        root, target = self._resolve_target(dom, node_id)
        self._apply_attrs(target, attrs)
        if text is not None:
            presentation.apply_text_and_children(target, text=text)
        elif children is not None:
            presentation.apply_text_and_children(target, children=children)

        dom[node_id] = ET.tostring(target, encoding="unicode")
        await self._notify_driver(driver, node_id, attrs=attrs, text=text, children=children)
        return dom[node_id]

    async def update_node(self, node_id, attrs=None, text=None, children=None):
        """Aggiorna un nodo XML salvato nel DOM in memoria, senza tocciare il file fisico."""
        driver = self._get_driver()
        if driver is None:
            raise RuntimeError("Nessun driver disponibile per manipolare il DOM")
        return await self._apply_to_dom(driver, node_id, attrs=attrs, text=text, children=children, action="update")

    async def create_node(self, node_id, tag, attrs=None, text=None, children=None):
        """Crea un nuovo nodo XML nel DOM."""
        driver = self._get_driver()
        if driver is None:
            raise RuntimeError("Nessun driver disponibile per manipolare il DOM")
        return await self._apply_to_dom(driver, node_id, attrs=attrs, text=text, children=children, action="create", tag=tag, new_id=node_id)

    async def replace_node(self, node_id, tag, attrs=None, text=None, children=None, new_id=None):
        """Sostituisce un nodo XML esistente nel DOM."""
        driver = self._get_driver()
        if driver is None:
            raise RuntimeError("Nessun driver disponibile per manipolare il DOM")
        return await self._apply_to_dom(driver, node_id, attrs=attrs, text=text, children=children, action="replace", tag=tag, new_id=new_id)

    async def remove_node(self, node_id):
        """Rimuove un nodo XML dal DOM."""
        driver = self._get_driver()
        if driver is None:
            raise RuntimeError("Nessun driver disponibile per manipolare il DOM")
        return await self._apply_to_dom(driver, node_id, action="remove")

    async def _insert_child(self, parent_id, child_tag, attrs=None, text=None, children=None, child_id=None, *, position="append", reference_id=None):
        driver = self._get_driver()
        if driver is None:
            raise RuntimeError("Nessun driver disponibile per manipolare il DOM")
        dom = self._get_dom(driver)
        _, parent = self._resolve_target(dom, parent_id)
        child = self._build_element(child_tag, attrs=attrs, text=text, children=children, node_id=child_id)

        if position == "append":
            parent.append(child)
        else:
            reference = self._resolve_target(dom, reference_id)[1] if reference_id else None
            if reference is None:
                raise ValueError("reference_id è obbligatorio per insert_before/insert_after")
            container = reference.getparent() if hasattr(reference, "getparent") else None
            if container is None:
                container = reference
            if container is reference:
                if position == "before":
                    container.insert(0, child)
                else:
                    container.append(child)
            else:
                index = list(container).index(reference)
                if position == "before":
                    container.insert(index, child)
                else:
                    container.insert(index + 1, child)

        dom[child_id or child.get("id") or f"child_{len(dom)}"] = ET.tostring(child, encoding="unicode")
        await self._notify_driver(driver, parent_id, attrs=None, text=None, children=None)
        return dom[child_id or child.get("id") or f"child_{len(dom)}"]

    async def append_child(self, parent_id, child_tag, attrs=None, text=None, children=None, child_id=None):
        """Aggiunge un figlio a un nodo esistente nel DOM."""
        return await self._insert_child(parent_id, child_tag, attrs=attrs, text=text, children=children, child_id=child_id, position="append")

    async def insert_before(self, reference_id, child_tag, attrs=None, text=None, children=None, child_id=None):
        """Inserisce un nuovo nodo prima di un riferimento nel DOM."""
        return await self._insert_child(reference_id, child_tag, attrs=attrs, text=text, children=children, child_id=child_id, position="before", reference_id=reference_id)

    async def insert_after(self, reference_id, child_tag, attrs=None, text=None, children=None, child_id=None):
        """Inserisce un nuovo nodo dopo un riferimento nel DOM."""
        return await self._insert_child(reference_id, child_tag, attrs=attrs, text=text, children=children, child_id=child_id, position="after", reference_id=reference_id)

    async def get_node(self, node_id):
        """Recupera un nodo XML dal DOM."""
        driver = self._get_driver()
        if driver is None:
            raise RuntimeError("Nessun driver disponibile per manipolare il DOM")
        dom = self._get_dom(driver)
        if node_id not in dom:
            raise KeyError(f"Nodo con id '{node_id}' non trovato nel DOM")
        return dom[node_id]

    async def manipulate_node(self, node_id, op="update", attrs=None, text=None, children=None, tag=None, new_id=None):
        """Compatibilità con il vecchio metodo generico: delega alle API specifiche."""
        if op == "create":
            return await self.create_node(node_id, tag, attrs=attrs, text=text, children=children)
        if op == "replace":
            return await self.replace_node(node_id, tag, attrs=attrs, text=text, children=children, new_id=new_id)
        if op == "remove":
            return await self.remove_node(node_id)
        if op == "update":
            return await self.update_node(node_id, attrs=attrs, text=text, children=children)
        raise ValueError(f"Azione DOM non supportata: {op}")