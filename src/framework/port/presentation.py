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
from urllib.parse import urlparse, parse_qs, urljoin
from enum import Enum

import os
import pathlib

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
    ROUTE = "route"
    ACT = "act"
    
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
    Tag.ACTION.value: _EVENTS | {Attribute.ROUTE.value:"action", Attribute.ACT.value:"method"} | _LAYOUT | _STYLE | {Attribute.POINTER.value:"pointer"}, 
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

    @abstractmethod
    async def render_reactive(self, *args, **kwargs):
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
        routes_cfg = self.defender.get_policy('presentation').get('routes', {}).values()
        
        try:
            for s in routes_cfg:
                # 1. Preparazione metadati e path di base
                view = f"application/view/page/{s['view']}" if s.get('view') else None
                path = s.get('path') or (view.replace('.xml', '') if view else "")
                
                # 2. Normalizzazione {$id} -> {id}
                path = re.sub(r'\{\$([a-zA-Z0-9_]+)\}', r'{\1}', path)
                
                # 3. Analisi opzioni multiple {a|b}
                matches = list(re.finditer(r'\{([a-zA-Z0-9_|]+)\}', path))
                # Estraiamo i set di opzioni solo se contengono '|'
                opt_sets = [m.group(1).split('|') for m in matches if '|' in m.group(1)]
                placeholders = [m.group(0) for m in matches if '|' in m.group(1)]

                # 4. Generazione combinazioni (se non ci sono opzioni, itera una volta sul path originale)
                combinations = itertools.product(*opt_sets) if opt_sets else [(None,)]
                
                for combo in combinations:
                    new_path = path
                    if opt_sets:
                        for i, val in enumerate(combo):
                            new_path = new_path.replace(placeholders[i], val, 1)
                    
                    # --- AGGIUNTA: CONVERSIONE IN REGEX ---
                    # Trasforma {id} in (?P<id>[^/]+) per catturare il valore durante il match
                    # Trasforma il path in una regex completa (es. ^/user/(?P<id>[^/]+)$)
                    pattern = re.sub(r'\{([a-zA-Z0-9_]+)\}', r'(?P<\1>[^/]+)', new_path)
                    regex_compiled = re.compile(f"^{pattern}$")
                    # --------------------------------------

                    # Salvataggio rotta arricchito (Raggruppato per Path e poi per Metodo)
                    method = s.get('method', 'GET').upper()
                    self.routes.setdefault(new_path, {})
                    self.routes[new_path][method] = {
                        **{k: s.get(k) for k in ['method', 'type', 'layout', 'controller', 'path']},
                        'view': view,
                        'pattern': regex_compiled # Fondamentale per il dispatcher
                    }

            print(f"[+] Routes: {list(self.routes.keys())}")
        except Exception as e:
            print(f"[!] Error: {e}")
            #raise e

    async def render_template(self, text=None,file=None,**constants):
        if text is None and file is None: raise Exception("No text or file provided")
        if text is None:
            text = await loader.resource(file)

        template = self.env.from_string(text)
        try:
            content = template.render(constants)
            xml = ET.fromstring(content)
            view = await self.render_node(text,xml,constants)
            return view
        except Exception as e:
            print(f"Si è verificato un errore durante il rendering del template: {e}",f"file: {file}")
            raise Exception(f"Si è verificato un errore durante il rendering del template: {e}",f"file: {file}")

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
        '''component_paths = [
            #f"src/application/view/components/{tag}.xml",
            f"src/application/view/component/{tag}.xml"
        ]'''

        base_path = os.environ.get("BASE_PATH", os.getcwd()) 

        # 2. Definiamo dove cercare i componenti (Percorso Assoluto per il controllo)
        search_paths = [
            os.path.join(base_path, "src/application/view/component", f"{tag}.xml"),
            os.path.join(base_path, "src/application/view/layout", f"{tag}.xml")
        ]

        for path in search_paths:
            if os.path.exists(path):
                # Rimuove "src/" per passarlo a render_template
                # poiché render_template aggiunge già "src/"
                #relative_path = path.replace("src/", "", 1)
                relative_path = path
                
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
        node_id = node.attrib.get('id')
        attributes = {}
        for k, v in node.attrib.items():
            attr_name = k.split('}')[-1] if '}' in k else k
            attributes[attr_name] = v
            
        if node_id:
            attributes['id'] = node_id
        if node.text:
            children.append(node.text)

        bind_var = attributes.pop("bind", None)
        if bind_var:
            if not node_id:
                raise Exception(f"Errore UI Reattiva: Un elemento con attributo 'bind' ({bind_var}) DEVE avere un attributo 'id' esplicito per permettere l'aggiornamento tramite WebSockets. Nodo incriminato: <{tag}>")
                
            if ":" in bind_var:
                dsl_alias, var_path = bind_var.split(":", 1)
                controller_file = f"src/application/controller/{dsl_alias}.dsl"
            else:
                var_path = bind_var
                controller_file = context.get("controller_file")

            # Assicuriamoci che l'executor e l'interpreter siano disponibili (in Adapter lo sono)
            if hasattr(self, "executor") and self.executor and hasattr(self.executor, "interpreter"):
                runner = self.executor.interpreter.runner
                
                # Se il path non è caricato e stiamo chiamando un alias specifico potremmo non avere le nodes caricate.
                # Per resilienza assumiamo che esista, ma gestiamo il caso.
                if controller_file and controller_file in runner.nodes:
                    bind_node_name = f"_auto_bind_{node_id}_{var_path}"
                    
                    if bind_node_name not in runner.nodes[controller_file]:
                        async def auto_bind_task(inputs):
                            sid = inputs.get("sid")
                            #print("#############################",inputs)
                            if sid:
                                await self.rebuild(node_id, sid, inputs,dsl_alias)
                            return True
                            
                        bind_node = {
                            "name":        bind_node_name,
                            "fn":          auto_bind_task,
                            "default":     None,
                            "deps":        [var_path],
                            "policy":      "all",
                            "meta":        False,
                            "trigger":     None,
                            "schedule":    None,
                            "duration":    None,
                            "timeout":     30,
                            "retries":     0,
                            "retry_delay": 0,
                            "when":        None,
                            "path":        bind_node_name,
                            "cache":       False,
                            "on_start":    None,
                            "on_success":  None,
                            "on_error":    None,
                            "on_end":      None,
                        }
                        
                        runner.attach_node(controller_file, bind_node)

        # mount_view: Il driver crea l'istanza del widget/tag
        return self.mount_tag(tag, attributes, children, in_svg)