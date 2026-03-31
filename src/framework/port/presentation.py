from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
from jinja2 import Environment, select_autoescape,FileSystemLoader,BaseLoader,ChoiceLoader,Template,DebugUndefined
from html import escape
import uuid
import untangle
import markupsafe
import re

import itertools

from enum import Enum

class Tag(Enum):
    WINDOW = "window"
    TEXT = "text"
    INPUT = "input"
    ACTION = "action"
    MEDIA = "media"
    CARD = "card"
    NAVIGATION = "navigation"
    GROUP = "group"
    ROW = "row"
    COLUMN = "column"
    STACK = "stack"
    CONTAINER = "container"
    DEFENDER = "defender"
    MESSENGER = "messenger"
    MESSAGE = "message"
    STOREKEEPER = "storekeeper"
    PRESENTER = "presenter"
    VIEW = "view"
    DIVIDER = "divider"
    ICON = "icon"
    ACCORDION = "accordion"
    RESOURCE = "resource"

class Attribute(Enum):
    ID = "id"
    TYPE = "type"
    SRC = "src"
    ALT = "alt"
    TITLE = "title"
    WIDTH = "width"
    HEIGHT = "height"
    CONTROLS = "controls"
    AUTOPLAY = "autoplay"
    LOOP = "loop"
    MUTED = "muted"
    CLASS = "class"
    NAME = "name"
    VALUE = "value"
    PLACEHOLDER = "placeholder"
    REQUIRED = "required"
    DISABLED = "disabled"
    READONLY = "readonly"
    MAX = "max"
    MIN = "min"
    SIZE = "size"
    MULTIPLE = "multiple"
    




class port(ABC):

    def initialize(self):
        self.components = {}
        self.data = {}
        self.routes = {}
        # DOM
        self.document = {}
        fs_loader = FileSystemLoader("src/application/view/layout/")

        #http_loader = MyLoader()
        #choice_loader = ChoiceLoader([fs_loader, http_loader])

        ui_kit = [
            'breadcrumb',
            #'table',
            'badge',
            'input',
            'action',
            'text',
            #'media',
            'window',
            'card',
            #'navigation',
            'pagination',
            'group',
            'row',
            'column',
            'container',
            'defender',
            'messenger',
            'message',
            'storekeeper',
            'presenter',
            'view',
            'divider',
            'icon',
            'accordion',
            #'resource',
        ]
        
        '''for widget in ui_kit:
            if widget not in self.WIDGETS:
                raise NotImplementedError(f"Tag '{widget}' non gestito in compose_view")'''
        
        self.env = Environment(loader=fs_loader,autoescape=select_autoescape(["html", "xml"]),undefined=DebugUndefined)
        #self.env.filters['route'] = language.route

    @abstractmethod
    async def mount_view(self, *services, **constants):
        pass

    @abstractmethod
    async def mount_route(self, *services, **constants):
        pass

    @abstractmethod
    async def mount_css(self, *services, **constants):
        pass

    @abstractmethod
    async def mount_tag(self, *services, **constants):
        pass

    @abstractmethod
    async def node_create(self, node, context):
        pass

    @abstractmethod
    async def node_update(self, node, context):
        pass

    @abstractmethod
    async def node_union(self, node, context):
        pass

    def mount_tag(self, tag, attrs={}, inner=[]):
        tag = tag.lower()
        if tag not in self.tags: raise Exception(f"Tag {tag} non trovato")
        tipo = attrs.get("type") or tag
        elemento = self.tags[tag].get(tipo)
        return self.node_create(elemento,attrs,inner)

    async def parse_route(self):
        # Regex per opzioni multiple senza virgolette (es. {a|b})
        regex_simple_options = r'\{([a-zA-Z0-9_|]+)\}'
        # Regex per parametri dinamici tipo {$id} -> {id}
        regex_dynamic_param = r'\{\$([a-zA-Z0-9_]+)\}'
        
        #rotta = f"application/policy/presentation/{self.config.get('project',).get('policy').get('presentation')}"
        rotta = f"src/application/policy/presentation/web.toml"
        file = await loader.resource(rotta)
        policy = await scheme.convert(file,dict,'toml')
        routes = policy.get('store').get('data').get('routes')
        try:
            for setting in routes:
                path_attribute = setting.get('path')
                method = setting.get('method')
                typee = setting.get('type')
                view = setting.get('view')
                layout = setting.get('layout')

                if view:
                    view = 'application/view/page/' + view
                    if not path_attribute:
                        path_attribute = view.replace('.xml', '')

                # 🔥 Normalizza subito i parametri dinamici {$id} → {id}
                path_attribute = re.sub(regex_dynamic_param, r'{\1}', path_attribute)

                # Trova tutte le parti dinamiche con opzioni multiple
                all_matches = re.finditer(regex_simple_options, path_attribute)
                dynamic_parts = []
                options_sets = []

                for match in all_matches:
                    dynamic_parts.append(match.group(0))  # es. "{means|product}"
                    options_str = match.group(1)          # es. "means|product"
                    options = options_str.split('|')      # es. ["means", "product"]
                    options_sets.append(options)

                if dynamic_parts:
                    # Caso 1: opzioni multiple → espandi combinazioni
                    for combination in itertools.product(*options_sets):
                        new_path = path_attribute
                        for i, part in enumerate(dynamic_parts):
                            # sostituisci solo le opzioni multiple, NON i parametri dinamici
                            if '|' in part:
                                new_path = new_path.replace(part, combination[i], 1)
                        self.routes[new_path] = {
                            'view': view, 'type': typee,
                            'method': method, 'layout': layout
                        }
                else:
                    # Caso 2/3: percorsi statici o con parametri dinamici
                    self.routes[path_attribute] = {
                        'view': view, 'type': typee,
                        'method': method, 'layout': layout
                    }

        except Exception as e:
            #print(f"Si è verificato un errore durante il parsing del file: {e}")
            pass
    
    async def render_template(self, **constants):
        if 'text' in constants:
            text = constants['text']
        else:
            text = await loader.resource("src/" + constants.get('file',''))

        template = self.env.from_string(text)
        if 'data' not in constants:
            constants['data'] = {}
        if 'view' not in constants:
            constants['view'] = {}

        if 'user' not in constants:
            user = await self.defender.whoami(identifier=constants.get('identifier'))
        else:
            user = {}
        
        content = template.render(constants|{'user':user})
        xml = ET.fromstring(content)
        view = await self.render_node(xml,constants|{'user':user})
        return view

    async def render_node(self, node, context):
        """Trasforma ricorsivamente i nodi XML in oggetti del Driver"""
        children = []
        for child in list(node):
            children.append(await self.render_node(child, context))

        # Se è il nodo root fittizio, restituiamo solo i figli uniti
        if node.tag == "root":
            return self.driver.combine_children(children)

        # Gestione ID e Stato
        node_id = node.attrib.get('id', str(uuid.uuid4()))
        attributes = dict(node.attrib)
        attributes['id'] = node_id
        if node.text:
            children.append(node.text)

        # mount_view: Il driver crea l'istanza del widget/tag
        return self.mount_tag(node.tag, attributes, children)