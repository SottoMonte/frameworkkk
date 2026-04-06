from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from jinja2 import Environment, select_autoescape,FileSystemLoader,BaseLoader,ChoiceLoader,Template,DebugUndefined
from html import escape
import uuid
import untangle
import markupsafe
import re

import itertools
import os

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
    GRID = "grid"
    SVG = "svg"
    CANVAS = "canvas"
    G = "g"
    DEFS = "defs"
    RECT = "rect"
    CIRCLE = "circle"
    PATH = "path"
    TEXT_SVG = "text_svg"
    TSPAN = "tspan"
    STYLE_SVG = "style_svg"
    FILTER = "filter"
    FE_GAUSSIAN_BLUR = "fegaussianblur"
    FE_OFFSET = "feoffset"
    FE_FLOOD = "feflood"
    FE_COMPOSITE = "fecomposite"
    FE_MERGE = "femerge"
    FE_MERGE_NODE = "femergenode"
    ANIMATE = "animate"
    ANIMATE_TRANSFORM = "animatetransform"
    STOP = "stop"
    LINEAR_GRADIENT = "lineargradient"
    RADIAL_GRADIENT = "radialgradient"
    POLYGON = "polygon"
    LINE = "line"
    FE_DROP_SHADOW = "fedropshadow"
    CLIP_PATH = "clippath"
    PATTERN = "pattern"
    RESOURCE = "resource"

class Attribute(Enum):
    CLICK = "click"
    DBLCLICK = "dblclick"
    MOUSEOVER = "mouseover"
    MOUSEOUT = "mouseout"
    KEYDOWN = "keydown"
    KEYUP = "keyup"
    KEYPRESS = "keypress"
    
    ID = "id"
    TYPE = "type"
    SRC = "src"
    ALT = "alt"
    TITLE = "title"
    WIDTH = "width"
    HEIGHT = "height"
    MIN_WIDTH = "min-width"
    MAX_WIDTH = "max-width"
    MIN_HEIGHT = "min-height"
    MAX_HEIGHT = "max-height"
    CONTROLS = "controls"
    AUTOPLAY = "autoplay"
    LOOP = "loop"
    MUTED = "muted"
    CLASS = "class"
    NAME = "name"
    VALUE = "value"
    COLOR = "color"
    PLACEHOLDER = "placeholder"
    REQUIRED = "required"
    DISABLED = "disabled"
    READONLY = "readonly"
    MAX = "max"
    MIN = "min"
    SIZE = "size"
    MULTIPLE = "multiple"
    STYLE = "style"
    JUSTIFY = "justify"
    ALIGN = "align"
    SPACING = "spacing"
    VARIANT = "variant"
    TONE = "tone"
    BACKGROUND = "background"
    BORDER = "border"
    RADIUS = "radius"
    SHADOW = "shadow"
    TEXT_ALIGN = "text-align"
    WEIGHT = "weight"
    POSITION = "position"
    RESPONSIVE = "responsive"
    PADDING = "padding"
    MARGIN = "margin"
    EXPAND = "expand"
    MATTER = "matter"
    POINTER = "pointer"
    THICKNESS = "thickness"
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    OVERFLOW = "overflow"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    TRUNCATE = "truncate"
    FONT = "font"
    VIEWBOX = "viewBox"
    D = "d"
    CX = "cx"
    CY = "cy"
    R = "r"
    RX = "rx"
    RY = "ry"
    X = "x"
    Y = "y"
    DX = "dx"
    DY = "dy"
    FILL = "fill"
    STROKE = "stroke"
    STROKE_WIDTH = "stroke-width"
    TRANSFORM = "transform"
    FILTER_ATTR = "filter"
    STD_DEVIATION = "stdDeviation"
    IN = "in"
    IN2 = "in2"
    OPERATOR = "operator"
    RESULT = "result"
    FLOOD_COLOR = "flood-color"
    FLOOD_OPACITY = "flood-opacity"
    TEXT_ANCHOR = "text-anchor"
    FONT_FAMILY = "font-family"
    FONT_SIZE = "font-size"
    FONT_WEIGHT = "font-weight"
    FONT_STYLE = "font-style"
    ATTRIBUTE_NAME = "attributeName"
    VALUES = "values"
    X1 = "x1"
    Y1 = "y1"
    X2 = "x2"
    Y2 = "y2"
    DUR = "dur"
    REPEAT_COUNT = "repeatCount"
    OPACITY = "opacity"
    POINTS = "points"
    OFFSET = "offset"
    STOP_COLOR = "stop-color"
    STOP_OPACITY = "stop-opacity"
    CLIP_PATH = "clip-path"
    CLIP_PATH_UNITS = "clipPathUnits"
    FROM = "from"
    TO = "to"
    BEGIN = "begin"
    ADDITIVE = "additive"
    ACCUMULATE = "accumulate"
    PATTERN_UNITS = "patternUnits"
    PATTERN_CONTENT_UNITS = "patternContentUnits"
    PATTERN_TRANSFORM = "patternTransform"
    PRESERVE_ASPECT_RATIO = "preserveAspectRatio"
    HREF = "href"
    

_IDENTITY = {a.value: a.value for a in [Attribute.ID, Attribute.CLASS]}
_MEDIA = {**_IDENTITY, **{a.value: a.value for a in [Attribute.SRC, Attribute.WIDTH, Attribute.HEIGHT, Attribute.ALT]}}
_FIELD = {**_IDENTITY, **{a.value: a.value for a in [Attribute.NAME, Attribute.VALUE, Attribute.PLACEHOLDER, Attribute.REQUIRED, Attribute.DISABLED, Attribute.READONLY, Attribute.MAX, Attribute.MIN, Attribute.MULTIPLE]}}
_MULTIMEDIA = {**_MEDIA, **{a.value: a.value for a in [Attribute.CONTROLS, Attribute.AUTOPLAY, Attribute.LOOP, Attribute.MUTED]}}
_LAYOUT_STATIC = {**_IDENTITY, **{a.value: a.value for a in [Attribute.WIDTH,Attribute.MAX_WIDTH, Attribute.MIN_WIDTH, Attribute.HEIGHT, Attribute.MAX_HEIGHT, Attribute.MIN_HEIGHT, Attribute.PADDING, Attribute.MARGIN, Attribute.OVERFLOW]}}
_LAYOUT = {**_LAYOUT_STATIC, **{a.value: a.value for a in [Attribute.EXPAND, Attribute.SPACING]}}
_LOCATION = {**_IDENTITY, **{a.value: a.value for a in [Attribute.JUSTIFY, Attribute.ALIGN, Attribute.POSITION, Attribute.TOP, Attribute.BOTTOM, Attribute.LEFT, Attribute.RIGHT]}}
_STYLE = {**_IDENTITY, **{a.value: a.value for a in [Attribute.BACKGROUND, Attribute.MATTER, Attribute.COLOR, Attribute.BORDER, Attribute.RADIUS, Attribute.SHADOW, Attribute.THICKNESS, Attribute.STYLE]}}
_TYPOGRAPHY = {**_LAYOUT, **{a.value: a.value for a in [Attribute.SIZE, Attribute.WEIGHT, Attribute.UPPERCASE, Attribute.LOWERCASE, Attribute.TRUNCATE, Attribute.FONT, Attribute.ALIGN]}}
_EVENTS = {
    Attribute.CLICK.value: f"data-{Attribute.CLICK.value}",
    Attribute.DBLCLICK.value: f"data-{Attribute.DBLCLICK.value}",
    Attribute.MOUSEOVER.value: f"data-{Attribute.MOUSEOVER.value}",
    Attribute.MOUSEOUT.value: f"data-{Attribute.MOUSEOUT.value}",
    Attribute.KEYDOWN.value: f"data-{Attribute.KEYDOWN.value}",
    Attribute.KEYUP.value: f"data-{Attribute.KEYUP.value}",
    Attribute.KEYPRESS.value: f"data-{Attribute.KEYPRESS.value}",
}

_ATTRIBUTES_SCHEMA = {
    Tag.WINDOW.value: _IDENTITY | _LOCATION | _LAYOUT | _STYLE | {Attribute.TITLE.value:"title", Attribute.POINTER.value:"pointer"},
    Tag.NAVIGATION.value: _IDENTITY | _LOCATION | _LAYOUT | _STYLE,
    Tag.TEXT.value: _TYPOGRAPHY | _STYLE, 
    Tag.INPUT.value: _EVENTS | _FIELD | _LAYOUT | _STYLE, 
    Tag.ACTION.value: _EVENTS | _MEDIA | _LAYOUT | _STYLE | {Attribute.POINTER.value:"pointer"}, 
    Tag.CONTAINER.value: _LAYOUT_STATIC | _LOCATION | _STYLE, 
    Tag.ROW.value: _LAYOUT | _LOCATION | _STYLE, 
    Tag.COLUMN.value: _LAYOUT | _LOCATION | _STYLE, 
    Tag.STACK.value: _LAYOUT | _LOCATION | _STYLE, 
    Tag.DIVIDER.value: _LOCATION | _LAYOUT | _STYLE | {Attribute.THICKNESS.value:"thickness"},
    Tag.ICON.value: _IDENTITY | {Attribute.NAME.value:"class", Attribute.SIZE.value:"size", Attribute.COLOR.value:"color"},
    Tag.GROUP.value: _IDENTITY | _LAYOUT | _LOCATION | _STYLE,
    Tag.ACCORDION.value: _IDENTITY | _LAYOUT | _STYLE,
    Tag.MEDIA.value: _IDENTITY | _MEDIA | _STYLE | _LAYOUT,
    Tag.CARD.value: _IDENTITY | _LAYOUT | _STYLE,
    Tag.CANVAS.value: _IDENTITY | _LAYOUT | _STYLE | _LOCATION,
    Tag.GRID.value: _IDENTITY | _LAYOUT | _STYLE | _LOCATION,
}

_SVG_ATTRIBUTES = {a.value: a.value for a in [
    Attribute.ID, Attribute.CLASS, Attribute.STYLE, Attribute.VIEWBOX, Attribute.D, Attribute.CX, Attribute.CY, Attribute.R, Attribute.RX, Attribute.RY,
    Attribute.X, Attribute.Y, Attribute.DX, Attribute.DY, Attribute.FILL, Attribute.STROKE, Attribute.STROKE_WIDTH, Attribute.TRANSFORM,
    Attribute.FILTER_ATTR, Attribute.STD_DEVIATION, Attribute.IN, Attribute.IN2, Attribute.OPERATOR, Attribute.RESULT,
    Attribute.FLOOD_COLOR, Attribute.FLOOD_OPACITY, Attribute.TEXT_ANCHOR, Attribute.FONT_FAMILY, Attribute.FONT_SIZE,
    Attribute.FONT_WEIGHT, Attribute.FONT_STYLE, Attribute.ATTRIBUTE_NAME, Attribute.VALUES, Attribute.DUR,
    Attribute.REPEAT_COUNT, Attribute.OPACITY, Attribute.POINTS, Attribute.OFFSET, Attribute.STOP_COLOR, Attribute.STOP_OPACITY,
    Attribute.WIDTH, Attribute.HEIGHT, Attribute.X1, Attribute.Y1, Attribute.X2, Attribute.Y2,
    Attribute.CLIP_PATH, Attribute.CLIP_PATH_UNITS, Attribute.FROM, Attribute.TO, Attribute.BEGIN,
    Attribute.ADDITIVE, Attribute.ACCUMULATE, Attribute.PATTERN_UNITS, Attribute.PATTERN_CONTENT_UNITS,
    Attribute.PATTERN_TRANSFORM, Attribute.PRESERVE_ASPECT_RATIO, Attribute.HREF
]}

_ATTRIBUTES_SCHEMA |= {
    Tag.SVG.value: _SVG_ATTRIBUTES,
    Tag.G.value: _SVG_ATTRIBUTES,
    Tag.DEFS.value: _SVG_ATTRIBUTES,
    Tag.RECT.value: _SVG_ATTRIBUTES,
    Tag.CIRCLE.value: _SVG_ATTRIBUTES,
    Tag.PATH.value: _SVG_ATTRIBUTES,
    Tag.TEXT_SVG.value: _SVG_ATTRIBUTES,
    Tag.TSPAN.value: _SVG_ATTRIBUTES,
    Tag.STYLE_SVG.value: _SVG_ATTRIBUTES | {Attribute.TYPE.value: "type"},
    Tag.FILTER.value: _SVG_ATTRIBUTES,
    Tag.FE_GAUSSIAN_BLUR.value: _SVG_ATTRIBUTES,
    Tag.FE_OFFSET.value: _SVG_ATTRIBUTES,
    Tag.FE_FLOOD.value: _SVG_ATTRIBUTES,
    Tag.FE_COMPOSITE.value: _SVG_ATTRIBUTES,
    Tag.FE_MERGE.value: _SVG_ATTRIBUTES,
    Tag.FE_MERGE_NODE.value: _SVG_ATTRIBUTES,
    Tag.ANIMATE.value: _SVG_ATTRIBUTES,
    Tag.ANIMATE_TRANSFORM.value: _SVG_ATTRIBUTES,
    Tag.STOP.value: _SVG_ATTRIBUTES,
    Tag.LINEAR_GRADIENT.value: _SVG_ATTRIBUTES,
    Tag.RADIAL_GRADIENT.value: _SVG_ATTRIBUTES,
    Tag.POLYGON.value: _SVG_ATTRIBUTES,
    Tag.LINE.value: _SVG_ATTRIBUTES,
    Tag.FE_DROP_SHADOW.value: _SVG_ATTRIBUTES,
    Tag.CLIP_PATH.value: _SVG_ATTRIBUTES,
    Tag.PATTERN.value: _SVG_ATTRIBUTES,
}



class port(ABC):

    def initialize(self):
        self.components = {}
        self.DOM = {}
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

    @abstractmethod
    async def rebuild(self, node_id, view=None, context=dict()):
        pass

    def combine_children(self, children):
        return "".join(children)

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

    def mount_tag(self, tag, attrs={}, inner=[], in_svg=False):
        if "}" in tag:
            tag = tag.split("}")[-1]
        tag = tag.lower()
        if in_svg and tag == "text":
            tag = Tag.TEXT_SVG.value
        elif in_svg and tag == "style":
            tag = Tag.STYLE_SVG.value
            
        if tag not in self.tags: raise Exception(f"Tag {tag} non trovato")
        tipo = attrs.get("type") or tag
        elemento = self.tags[tag].get(tipo) or self.tags[tag].get(tag)
        if elemento is None: raise Exception(f"Tipo {tipo} non trovato in {tag}")
        schema = _ATTRIBUTES_SCHEMA.get(tag) or {}
        new_attrs = {}
        for attr in attrs:
            if attr not in schema: 
                #print(f"Attributo {attr} non valido per il tag {tag}")
                pass
            else:
                new_attrs[schema[attr]] = attrs[attr]

        #print(tag,new_attrs)
        return self.node_create(elemento,new_attrs,inner)

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
                controller = setting.get('controller')

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
                            'method': method, 'layout': layout,
                            'controller': controller
                        }
                else:
                    # Caso 2/3: percorsi statici o con parametri dinamici
                    self.routes[path_attribute] = {
                        'view': view, 'type': typee,
                        'method': method, 'layout': layout,
                        'controller': controller
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
        try:
            content = template.render(constants|{'user':user})
            xml = ET.fromstring(content)
            view = await self.render_node(text,xml,constants|{'user':user})
            return view
        except Exception as e:
            print(f"Si è verificato un errore durante il rendering del template: {e}",f"file: {constants.get('file','')}")
            raise Exception(f"Si è verificato un errore durante il rendering del template: {e}",f"file: {constants.get('file','')}")

    async def render_node(self, parent,node, context):
        """Trasforma ricorsivamente i nodi XML in oggetti del Driver"""
        tag = node.tag.split('}')[-1] if '}' in node.tag else node.tag
        in_svg = context.get('in_svg', False)
        if tag.lower() == "svg":
            in_svg = True

        ID = node.attrib.get('id')
        if ID != None and ID not in self.DOM:
            self.DOM[ID] = self.estrai_da_xml_string(parent,ID)

        # Controllo se il tag è un componente (custom tag)
        component_paths = [
            f"src/application/view/components/{tag}.xml",
            f"src/application/view/component/{tag}.xml"
        ]

        for path in component_paths:
            if os.path.exists(path):
                # Rimuove "src/" per passarlo a render_template
                # poiché render_template aggiunge già "src/"
                relative_path = path.replace("src/", "", 1)
                
                # 1. Cattura i nodi figli originali come stringa XML pura (non renderizzata)
                # Questo evita che il parser XML veda tag HTML durante l'espansione
                inner_xml = "".join([ET.tostring(child, encoding='unicode') for child in list(node)])
                
                # 2. Prepara ID e Attributi
                node_id = node.attrib.get('id', str(uuid.uuid4()))
                attributes = {k.split('}')[-1]: v for k, v in node.attrib.items()}
                attributes['id'] = node_id
                
                # 3. Renderizza il componente iniettando l'XML non ancora processato
                return await self.render_template(
                    **(context | {
                        'file': relative_path,
                        'inner': inner_xml,
                        'component': {
                            'id': node_id,
                            'attributes': attributes,
                            'inner': inner_xml
                        }
                    })
                )

        # Gestione Standard dei tag DSL
        children = []
        new_context = context.copy()
        new_context['in_svg'] = in_svg
        for child in list(node):
            children.append(await self.render_node(parent,child, new_context))

        # Se è il nodo root fittizio o uno slot residuo, restituiamo solo i figli uniti
        if tag == "root" :
            return self.combine_children(children)

        # Gestione ID e Stato
        node_id = node.attrib.get('id', str(uuid.uuid4()))
        attributes = {}
        for k, v in node.attrib.items():
            attr_name = k.split('}')[-1] if '}' in k else k
            attributes[attr_name] = v
        attributes['id'] = node_id
        if node.text:
            children.append(node.text)

        # mount_view: Il driver crea l'istanza del widget/tag
        return self.mount_tag(tag, attributes, children, in_svg)