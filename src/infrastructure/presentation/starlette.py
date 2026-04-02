import uuid
import asyncio
from html import escape
import re
import json
from datetime import datetime
from urllib.parse import urlparse, urlunparse, ParseResult,parse_qs
import htpy
from markupsafe import Markup

try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse,HTMLResponse,RedirectResponse
    from starlette.routing import Route,Mount,WebSocketRoute
    from starlette.middleware import Middleware
    from starlette.websockets import WebSocket
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
    #from starlette.middleware.csrf import CSRFMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.staticfiles import StaticFiles

    import os
    import uuid
    #import uvicorn
    from uvicorn import Config, Server

    # Auth 
    #from starlette.middleware.sessions import SessionMiddleware
    from datetime import timedelta
    import secrets
    #from starlette_login.middleware import AuthenticationMiddleware

    #
    from starlette.requests import HTTPConnection
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from starlette.datastructures import MutableHeaders
    import http.cookies
    import markupsafe
    from bs4 import BeautifulSoup
    import paramiko
    import asyncio

    '''class NoCacheMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Server"] = "Starlette-Test"
            return response'''

except Exception as e:
    #import starlette
    import markupsafe
    from bs4 import BeautifulSoup
    
    import xml.etree.ElementTree as ET
    from xml.sax.saxutils import escape


# --- Configurazione Programmatica Attributi ---

mapping_attributes = {
    presentation.Attribute.WIDTH.value: lambda x: {
        "full": "w-full",
        "1/2": "w-1/2",
        "1/3": "w-1/3",
        "1/4": "w-1/4",
        "auto": "w-auto",
        True:f"w-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.HEIGHT.value: lambda x: {
        "full": "h-full",
        "1/2": "h-1/2",
        "1/3": "h-1/3",
        "1/4": "h-1/4",
        "auto": "h-auto",
        True:f"h-[{x}]"
    }.get(True if '%' in x or 'px' in x else x),
    presentation.Attribute.MAX_HEIGHT.value: lambda x: {
        True:f"max-h-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.MIN_HEIGHT.value: lambda x: {
        True:f"min-h-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.MAX_WIDTH.value: lambda x: {
        True:f"max-w-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.MIN_WIDTH.value: lambda x: {
        True:f"min-w-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.PADDING.value: lambda x: {
        False:f"p-[{x}]",
        True:" ".join(f"{p}-[{v}]" for p, v in zip(['pt','pb','pl','pr'] if len(x.split(',')) > 2 else ['py', 'px'], x.split(',')))
    }.get(True if ',' in x else False, ""),
    presentation.Attribute.MARGIN.value: lambda x: {
        False:f"m-[{x}]",
        True:" ".join(f"{p}-[{v}]" for p, v in zip(['mt','mb','ml','mr'] if len(x.split(',')) > 2 else ['my', 'mx'], x.split(',')))
    }.get(True if ',' in x else False, ""),
    presentation.Attribute.EXPAND.value: lambda x: {
        "true":"flex-1",
        "false":""
    }.get(x, "false"),
    presentation.Attribute.OVERFLOW.value: lambda x: {
        "auto":"overflow-auto",
        "hidden":"overflow-hidden",
        "visible":"overflow-visible",
        "scroll":"overflow-scroll",
        "clip":"overflow-clip",
        "none":"overflow-hidden",
    }.get(x, ""),
    presentation.Attribute.COLOR.value: lambda x: {
        "primary":"text-primary",
        "secondary":"text-secondary",
        "success":"text-success",
        "danger":"text-danger",
        "warning":"text-warning",
        "info":"text-info",
        "light":"text-light",
        "dark":"text-dark",
        True:f"text-[{x}]"
    }.get(True if '#' in x else x, ""),
    "color.border": lambda x: f"border-[{x}]" if '#' in x else "",
    presentation.Attribute.SPACING.value: lambda x: {
        True:f"gap-[{x}]"
    }.get(True if '%' in x or 'px' in x else False, ""),
    presentation.Attribute.JUSTIFY.value: lambda x: {
        "start": "justify-start",
        "end": "justify-end",
        "center": "justify-center",
        "between": "justify-between",
        "around": "justify-around",
        "evenly": "justify-evenly",
    }.get(x, ""),
    presentation.Attribute.ALIGN.value: lambda x: {
        "start": "items-start",
        "end": "items-end",
        "center": "items-center",
        "stretch": "items-stretch",
    }.get(x, ""),
    presentation.Attribute.POSITION.value: lambda x: {
        "static": "static",
        "relative": "relative",
        "absolute": "absolute",
        "fixed": "fixed",
        "sticky": "sticky",
    }.get(x, ""),
    presentation.Attribute.RADIUS.value: lambda x: {
        "none":"rounded-none",
        "small":"rounded-sm",
        "medium":"rounded-md",
        "large":"rounded-lg",
        "full":"rounded-full",
    }.get(x, ""),
    presentation.Attribute.BORDER.value: lambda x: {
        "none":"border-none",
        False:f"border-[{x}]",
        True:" ".join(f"{p}-[{v}]" for p, v in zip(['border-t','border-b','border-l','border-r'] if len(x.split(',')) > 2 else ['border-y', 'border-x'], x.split(',')))
    }.get(True if ',' in x else False, ""),
    presentation.Attribute.SHADOW.value: lambda x: {
        "none":"shadow-none",
        "min":"shadow-sm",
        "medium":"shadow-md",
        "large":"shadow-lg",
        "max":"shadow-xl",
    }.get(x, ""),
    presentation.Attribute.BACKGROUND.value: lambda x: {
        "none":"bg-transparent",
        False:f"bg-gradient-to-r from-[{x.split(',')[0]}] to-[{x.split(',')[-1]}]",
        True:f"bg-[{x}]"
    }.get(False if ',' in x else True, ""),
    presentation.Attribute.MATTER.value: lambda x: {
        "glass":"backdrop-blur-md",
        "glass-min":"backdrop-blur-sm",
        "glass-medium":"backdrop-blur-lg",
        "glass-max":"backdrop-blur-xl",
    }.get(x, ""),
    presentation.Attribute.POINTER.value: lambda x: {
        "auto":"cursor-auto",
        "default":"cursor-default",
        "pointer":"cursor-pointer",
        "wait":"cursor-wait",
        "text":"cursor-text",
        "move":"cursor-move",
        "not-allowed":"cursor-not-allowed",
        "help":"cursor-help",
        "crosshair":"cursor-crosshair",
        "zoom-in":"cursor-zoom-in",
        "zoom-out":"cursor-zoom-out",
        "grab":"cursor-grab",
        "grabbing":"cursor-grabbing",
        "col-resize":"cursor-col-resize",
        "row-resize":"cursor-row-resize",
        "n-resize":"cursor-n-resize",
        "s-resize":"cursor-s-resize",
        "e-resize":"cursor-e-resize",
        "w-resize":"cursor-w-resize",
        "ne-resize":"cursor-ne-resize",
        "nw-resize":"cursor-nw-resize",
        "se-resize":"cursor-se-resize",
        "sw-resize":"cursor-sw-resize",
    }.get(x, ""),
    presentation.Attribute.TOP.value: lambda x: {
        True:f"top-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.BOTTOM.value: lambda x: {
        True:f"bottom-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.LEFT.value: lambda x: {
        True:f"left-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.RIGHT.value: lambda x: {
        True:f"right-[{x}]"
    }.get(True if '%' in x or 'px' in x else x, ""),
    presentation.Attribute.SIZE.value: lambda x: {
        "min":"text-xs",
        "small":"text-sm",
        "medium":"text-base",
        "large":"text-lg",
        "max":"text-xl",
        True:f"text-[{x}]"
    }.get(True if '%' in x or 'px' in x or 'em' in x else x, ""),
    presentation.Attribute.UPPERCASE.value: lambda x: {
        "true":"uppercase",
        "false":""
    }.get(x, ""),
    presentation.Attribute.LOWERCASE.value: lambda x: {
        "true":"lowercase",
        "false":""
    }.get(x, ""),
    presentation.Attribute.TRUNCATE.value: lambda x: {
        "true":"truncate",
        "false":""
    }.get(x, ""),
    presentation.Attribute.FONT.value: lambda x: f"font-{x}",
    "spacing.text": lambda x: {
        "min":"tracking-tighter",
        "normal":"tracking-normal",
        "max":"tracking-wide",
        True:f"tracking-[{x}]"
    }.get(True if '%' in x or 'px' in x or 'em' in x else x, ""),
    "height.text": lambda x: f"leading-[{x}]", 
    "align.text": lambda x: {
        "left":"text-left",
        "center":"text-center",
        "right":"text-right",
    }.get(x, ""),
}

def attrs(tag_key, input_data, classe=None):
    # 1. Prendi gli attributi grezzi passati dall'utente
    raw_attrs = input_data.get("attrs", {})
    if classe:
        raw_attrs["class"] = classe + " " + raw_attrs.get("class", "")
    
    classe = raw_attrs.get("class", "")

    if tag_key not in [presentation.Tag.TEXT.value] and (any(attr in raw_attrs for attr in [presentation.Attribute.JUSTIFY.value, presentation.Attribute.ALIGN.value,presentation.Attribute.EXPAND.value,presentation.Attribute.SPACING.value]) or tag_key in [presentation.Tag.ROW.value, presentation.Tag.COLUMN.value]):
        classe += " flex"

    if presentation.Attribute.COLOR.value in raw_attrs and presentation.Attribute.BORDER.value in raw_attrs:
        raw_attrs["color.border"] = raw_attrs[presentation.Attribute.COLOR.value]

    if presentation.Attribute.THICKNESS.value in raw_attrs and tag_key == presentation.Tag.DIVIDER.value:
        tipo = raw_attrs.get(presentation.Attribute.TYPE.value, "horizontal")
        if tipo == "horizontal":
            raw_attrs[presentation.Attribute.HEIGHT.value] = raw_attrs[presentation.Attribute.THICKNESS.value]
        else:
            raw_attrs[presentation.Attribute.WIDTH.value] = raw_attrs[presentation.Attribute.THICKNESS.value]
        raw_attrs.pop(presentation.Attribute.THICKNESS.value)

    if presentation.Attribute.SPACING.value in raw_attrs and tag_key == presentation.Tag.TEXT.value:
        raw_attrs["spacing.text"] = raw_attrs[presentation.Attribute.SPACING.value]
        raw_attrs.pop(presentation.Attribute.SPACING.value)

    if presentation.Attribute.HEIGHT.value in raw_attrs and tag_key == presentation.Tag.TEXT.value:
        raw_attrs["height.text"] = raw_attrs[presentation.Attribute.HEIGHT.value]
        raw_attrs.pop(presentation.Attribute.HEIGHT.value)

    if presentation.Attribute.ALIGN.value in raw_attrs and tag_key == presentation.Tag.TEXT.value:
        raw_attrs["align.text"] = raw_attrs[presentation.Attribute.ALIGN.value]
        raw_attrs.pop(presentation.Attribute.ALIGN.value)

    is_svg = tag_key in [
        presentation.Tag.SVG.value, presentation.Tag.G.value, presentation.Tag.DEFS.value, presentation.Tag.RECT.value,
        presentation.Tag.CIRCLE.value, presentation.Tag.PATH.value, presentation.Tag.TEXT_SVG.value, presentation.Tag.TSPAN.value,
        presentation.Tag.STYLE_SVG.value, presentation.Tag.FILTER.value, presentation.Tag.FE_GAUSSIAN_BLUR.value,
        presentation.Tag.FE_OFFSET.value, presentation.Tag.FE_FLOOD.value, presentation.Tag.FE_COMPOSITE.value,
        presentation.Tag.FE_MERGE.value, presentation.Tag.FE_MERGE_NODE.value, presentation.Tag.ANIMATE.value,
        presentation.Tag.STOP.value, presentation.Tag.POLYGON.value, presentation.Tag.LINE.value,
        presentation.Tag.FE_DROP_SHADOW.value
    ]

    for attr in list(raw_attrs.keys()):
        if attr not in mapping_attributes:
            continue
        
        # In SVG we might want to keep width/height as attributes instead of classes
        if is_svg and attr in [presentation.Attribute.WIDTH.value, presentation.Attribute.HEIGHT.value]:
            continue

        valore = mapping_attributes[attr](raw_attrs[attr])
        if valore:
            classe += " " + valore
            raw_attrs.pop(attr)
    
    return {
        "class": classe,
        **{k: v for k, v in raw_attrs.items() if k != "class"}
    }

class Adapter(presentation.port):
    # --- Configurazione Tag ---
    tags = {
        presentation.Tag.WINDOW.value: {
            "page": lambda x: htpy.html[
                htpy.head[
                    htpy.meta(charset="utf-8"),
                    htpy.meta(name="viewport", content="width=device-width, initial-scale=1"),
                    htpy.title[x.get("attrs", {}).get("title", "Today's menu")],
                    #htpy.link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"),
                    htpy.link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"),
                    htpy.script(src="https://cdn.tailwindcss.com"),
                ],
                htpy.body(**attrs(presentation.Tag.WINDOW.value, x))[
                    [Markup(i) for i in x['inner']],
                    #htpy.script(src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js")
                ]
            ],
            "dialog": lambda x: htpy.div(class_="modal fade", id=x.get("attrs", {}).get("id", "myModal"), tabindex="-1", aria_hidden="true")[
                htpy.div(class_="modal-dialog")[
                    htpy.div(class_="modal-content")[
                        htpy.div(class_="modal-header")[
                            htpy.h5(class_="modal-title")[x.get("attrs", {}).get("title", "")],
                            htpy.button(type="button", class_="btn-close", data_bs_dismiss="modal", aria_label="Close")
                        ],
                        htpy.div(class_="modal-body")[[Markup(i) for i in x['inner']]],
                        htpy.div(class_="modal-footer")[
                            htpy.button(type="button", class_="btn btn-secondary", data_bs_dismiss="modal")["Chiudi"]
                        ]
                    ]
                ]
            ],
            "still": lambda x: htpy.div(class_=f"offcanvas offcanvas-{x.get('attrs', {}).get('alignment-content', 'start')}", tabindex="-1", id=x.get('attrs', {}).get('id', 'offcanvasMenu'), aria_labelledby=f"{x.get('attrs', {}).get('id', 'offcanvasMenu')}Label")[
                htpy.div(class_="offcanvas-header")[
                    htpy.h5(class_="offcanvas-title", id=f"{x.get('attrs', {}).get('id', 'offcanvasMenu')}Label")[x.get("attrs", {}).get("title", "")],
                    htpy.button(type="button", class_="btn-close", data_bs_dismiss="offcanvas", aria_label="Close")
                ],
                htpy.div(class_="offcanvas-body")[[Markup(i) for i in x['inner']]]
            ],
            "embed": lambda x: htpy.div(**attrs("embed", x))[[Markup(i) for i in x['inner']]],
        },
        presentation.Tag.TEXT.value: {
            "text": lambda x: htpy.span(**attrs("text", x,"text-xs"))[[Markup(i) for i in x['inner']]],
            "input": lambda x: htpy.span(**attrs("input", x, 'input-group-text'))[[Markup(i) for i in x['inner']]],
            "h1": lambda x: htpy.h1(**attrs("text", x, "text-6xl"))[[Markup(i) for i in x['inner']]],
            "h2": lambda x: htpy.h2(**attrs("text", x, "text-5xl"))[[Markup(i) for i in x['inner']]],
            "h3": lambda x: htpy.h3(**attrs("text", x, "text-4xl"))[[Markup(i) for i in x['inner']]],
            "h4": lambda x: htpy.h4(**attrs("text", x, "text-3xl"))[[Markup(i) for i in x['inner']]],
            "h5": lambda x: htpy.h5(**attrs("text", x, "text-2xl"))[[Markup(i) for i in x['inner']]],
            "h6": lambda x: htpy.h6(**attrs("text", x, "text-xl"))[[Markup(i) for i in x['inner']]],
            "p": lambda x: htpy.p(**attrs("text", x, "text-base"))[[Markup(i) for i in x['inner']]],
            "span": lambda x: htpy.span(**attrs("text", x, "text-transparent bg-clip-text"))[[Markup(i) for i in x['inner']]],
            "mark": lambda x: htpy.mark(**attrs("mark", x, "text-transparent bg-clip-text"))[[Markup(i) for i in x['inner']]],
            "code": lambda x: htpy.code(**attrs("code", x))[[Markup(i) for i in x['inner']]],
            "pre": lambda x: htpy.pre(**attrs("pre", x))[[Markup(i) for i in x['inner']]],
            "blockquote": lambda x: htpy.blockquote(**attrs("blockquote", x))[[Markup(i) for i in x['inner']]],
            "cite": lambda x: htpy.cite(**attrs("cite", x))[[Markup(i) for i in x['inner']]],
            "abbr": lambda x: htpy.abbr(**attrs("abbr", x))[[Markup(i) for i in x['inner']]],
            "time": lambda x: htpy.time(**attrs("time", x))[[Markup(i) for i in x['inner']]],
        },
        presentation.Tag.INPUT.value: {
            "input": lambda x: htpy.input(type="text", class_="form-control"),
            "select": lambda x: htpy.select(class_="form-select"),
            "textarea": lambda x: htpy.textarea(class_="form-control"),
            "text": lambda x: htpy.input(type="text", class_="form-control"), 
            "password": lambda x: htpy.input(type="password", class_="form-control"),
            "switch": lambda x: htpy.input(type="checkbox", class_="form-switch"), 
            "checkbox": lambda x: htpy.input(type="checkbox", class_="form-check-input"),
            "radio": lambda x: htpy.input(type="radio", class_="form-check-input"), 
            "range": lambda x: htpy.input(class_="form-range", type="range"),
            "color": lambda x: htpy.input(type="color", class_="form-control"), 
            "date": lambda x: htpy.input(type="date", class_="form-control"), 
            "month": lambda x: htpy.input(type="month", class_="form-control"), 
            "week": lambda x: htpy.input(type="week", class_="form-control"), 
            "time": lambda x: htpy.input(type="time", class_="form-control"),
            "number": lambda x: htpy.input(type="number", class_="form-control"), 
            "email": lambda x: htpy.input(type="email", class_="form-control"), 
            "url": lambda x: htpy.input(type="url", class_="form-control"),
            "search": lambda x: htpy.input(type="search", class_="form-control"),
            "tel": lambda x: htpy.input(type="tel", class_="form-control"), 
            "dropdown": lambda x: htpy.select(class_="form-select"),
            "file": lambda x: htpy.input(type="file", class_="form-control"),
            "hidden": lambda x: htpy.input(type="hidden"),
        },
        presentation.Tag.ACTION.value: {
            "form": lambda x: htpy.form(class_="form-control")[[Markup(i) for i in x['inner']]],
            "action": lambda x: htpy.button(**attrs("action", x, "px-4 py-2 hover:opacity-80 transition-opacity"))[[Markup(i) for i in x['inner']]], 
            "button": lambda x: htpy.button(**attrs("button", x, "px-4 py-2 hover:opacity-80 transition-opacity"))[[Markup(i) for i in x['inner']]], 
            "submit": lambda x: htpy.input(**attrs("submit", x, "btn btn-primary"))[[Markup(i) for i in x['inner']]], 
            "reset": lambda x: htpy.input(**attrs("reset", x, "btn btn-secondary"))[[Markup(i) for i in x['inner']]],
            "link": lambda x: htpy.a(**attrs("link", x, "btn link"))[[Markup(i) for i in x['inner']]],
        },
        presentation.Tag.MEDIA.value: {
            "media": lambda x: htpy.img(**attrs("media", x)), 
            "img": lambda x: htpy.img(**attrs("img", x)), 
            "video": lambda x: htpy.video(**attrs("video", x)), 
            "audio": lambda x: htpy.audio(**attrs("audio", x)), 
            "embed": lambda x: htpy.embed(**attrs("embed", x)),
            "carousel": lambda x: htpy.div(".carousel"), 
            "map": lambda x: htpy.div(".map"), 
            "icon": lambda x: htpy.i(".bi")
        },
        presentation.Tag.CONTAINER.value: {
            "container": lambda x: htpy.div(**attrs("container", x))[[Markup(i) for i in x['inner']]], 
            "fluid": lambda x: htpy.div(**attrs("fluid", x))[[Markup(i) for i in x['inner']]]
        },
        presentation.Tag.ROW.value: {
            "row": lambda x: htpy.div(**attrs("row", x, "flex-row"))[[Markup(i) for i in x['inner']]]
        },
        presentation.Tag.COLUMN.value: { 
            "column": lambda x: htpy.div(**attrs("column", x, "flex-col"))[[Markup(i) for i in x['inner']]]
        },
        presentation.Tag.STACK.value: { 
            "stack": lambda x: htpy.div(".position-relative")[[Markup(i) for i in x['inner']]]
        },
        presentation.Tag.DIVIDER.value: { 
            "divider": lambda x: htpy.hr(**attrs("divider", x,"w-full border-none")),
            "vertical": lambda x: htpy.div(**attrs("vertical", x,"h-full border-none")),
            "horizontal": lambda x: htpy.hr(**attrs("horizontal", x,"w-full border-none"))
        },
        presentation.Tag.ICON.value: { 
            "icon": lambda x: htpy.i(**attrs("icon", x)),
            "bi": lambda x: htpy.i(**attrs("icon", x)),
            "fa": lambda x: htpy.i(**attrs("icon", x)),
        },
        presentation.Tag.NAVIGATION.value: {
            "navigation": lambda x: htpy.nav(**attrs("navigation", x,""))[[Markup(i) for i in x['inner']]],
            "bar": lambda x: htpy.nav(**attrs("bar", x,"nav"))[[Markup(i) for i in x['inner']]],
            "app": lambda x: htpy.nav(**attrs("app", x,""))[[Markup(i) for i in x['inner']]],
            "breadcrumb": lambda x: htpy.nav(**attrs("breadcrumb", x,"breadcrumb"))[[Markup(i) for i in x['inner']]],
            "tab": lambda x: htpy.nav(**attrs("tab", x,"nav-tabs"))[[Markup(i) for i in x['inner']]],
        },
        presentation.Tag.GROUP.value: {
            "input": lambda x: htpy.div(**attrs("input", x,'input-group'))[[Markup(i) for i in x['inner']]],
            "action": lambda x: htpy.div(**attrs("button", x,'btn-group'))[[Markup(i) for i in x['inner']]],
            "card": lambda x: htpy.div(**attrs("card", x,'card-group'))[[Markup(i) for i in x['inner']]],
            "list": lambda x: htpy.ul(**attrs("group", x,'flex-col'))[[Markup(htpy.li[i]) for i in x['inner']]],
            "tab": lambda x: htpy.ul(**attrs("tab", x,'nav-tabs'))[[Markup(htpy.li('.nav-item')[i]) for i in x['inner']]],
            "dropdown": lambda x: htpy.div(**attrs("dropdown", x,'dropdown'))[[Markup(i) for i in x['inner']]],
        },
        presentation.Tag.SVG.value: {"svg": lambda x: htpy.Element("svg")(**attrs(presentation.Tag.SVG.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.G.value: {"g": lambda x: htpy.Element("g")(**attrs(presentation.Tag.G.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.DEFS.value: {"defs": lambda x: htpy.Element("defs")(**attrs(presentation.Tag.DEFS.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.STYLE_SVG.value: {
            "style_svg": lambda x: htpy.Element("style")(**attrs(presentation.Tag.STYLE_SVG.value, x))[[Markup(i) for i in x['inner']]],
            "text/css": lambda x: htpy.Element("style")(**attrs(presentation.Tag.STYLE_SVG.value, x))[[Markup(i) for i in x['inner']]]
        },
        presentation.Tag.RECT.value: {"rect": lambda x: htpy.Element("rect")(**attrs(presentation.Tag.RECT.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.CIRCLE.value: {"circle": lambda x: htpy.Element("circle")(**attrs(presentation.Tag.CIRCLE.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.PATH.value: {"path": lambda x: htpy.Element("path")(**attrs(presentation.Tag.PATH.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.TEXT_SVG.value: {"text_svg": lambda x: htpy.Element("text")(**attrs(presentation.Tag.TEXT_SVG.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.TSPAN.value: {"tspan": lambda x: htpy.Element("tspan")(**attrs(presentation.Tag.TSPAN.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FILTER.value: {"filter": lambda x: htpy.Element("filter")(**attrs(presentation.Tag.FILTER.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FE_GAUSSIAN_BLUR.value: {"fegaussianblur": lambda x: htpy.Element("feGaussianBlur")(**attrs(presentation.Tag.FE_GAUSSIAN_BLUR.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FE_OFFSET.value: {"feoffset": lambda x: htpy.Element("feOffset")(**attrs(presentation.Tag.FE_OFFSET.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FE_FLOOD.value: {"feflood": lambda x: htpy.Element("feFlood")(**attrs(presentation.Tag.FE_FLOOD.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FE_COMPOSITE.value: {"fecomposite": lambda x: htpy.Element("feComposite")(**attrs(presentation.Tag.FE_COMPOSITE.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FE_MERGE.value: {"femerge": lambda x: htpy.Element("feMerge")(**attrs(presentation.Tag.FE_MERGE.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FE_MERGE_NODE.value: {"femergenode": lambda x: htpy.Element("feMergeNode")(**attrs(presentation.Tag.FE_MERGE_NODE.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.ANIMATE.value: {"animate": lambda x: htpy.Element("animate")(**attrs(presentation.Tag.ANIMATE.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.STOP.value: {"stop": lambda x: htpy.Element("stop")(**attrs(presentation.Tag.STOP.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.LINEAR_GRADIENT.value: {"lineargradient": lambda x: htpy.Element("linearGradient")(**attrs(presentation.Tag.LINEAR_GRADIENT.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.RADIAL_GRADIENT.value: {"radialgradient": lambda x: htpy.Element("radialGradient")(**attrs(presentation.Tag.RADIAL_GRADIENT.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.POLYGON.value: {"polygon": lambda x: htpy.Element("polygon")(**attrs(presentation.Tag.POLYGON.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.LINE.value: {"line": lambda x: htpy.Element("line")(**attrs(presentation.Tag.LINE.value, x))[[Markup(i) for i in x['inner']]]},
        presentation.Tag.FE_DROP_SHADOW.value: {"fedropshadow": lambda x: htpy.Element("feDropShadow")(**attrs(presentation.Tag.FE_DROP_SHADOW.value, x))[[Markup(i) for i in x['inner']]]},
    }

    def __init__(self,**constants):
        self.config = constants
        self.messenger = constants.get('messenger')
        self.defender = constants.get('defender')
        self.views = dict({})
        self.ssh = {}
        cwd = os.getcwd()
        self.initialize()
        self.routes_static=[
            Mount('/static', app=StaticFiles(directory=f'{cwd}/public/'), name="static"),
            Mount('/framework', app=StaticFiles(directory=f'{cwd}/src/framework'), name="y"),
            Mount('/application', app=StaticFiles(directory=f'{cwd}/src/application'), name="z"),
            Mount('/infrastructure', app=StaticFiles(directory=f'{cwd}/src/infrastructure'), name="x"),
            #WebSocketRoute("/messenger", self.websocket, name="messenger"),
            #WebSocketRoute("/ssh", self.websocketssh, name="ssh"),
        ]
        
        self.middleware_static = [
            Middleware(SessionMiddleware, session_cookie="session_state",secret_key=self.config.get('project',{}).get('key', 'default_key')),
            Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'], allow_credentials=True),
            #Middleware(NoCacheMiddleware),
            #Middleware(CSRFMiddleware, secret=self.config['project']['key']),
            #Middleware(AuthorizationMiddleware, manager=defender)
        ]

    async def start(self):
        loop = asyncio.get_event_loop()
        print("Starlette: Inizializzazione in corso...")
        await self.parse_route()
        self.mount_route(self.routes_static) # 'routes' deve essere accessibile qui
        # Inizializza l'applicazione Starlette con rotte e middleware
        self.app = Starlette(debug=True, routes=self.routes_static, middleware=self.middleware_static)
        #print(di['message'][0].logger,'###########')
        # Parametri di configurazione base per Uvicorn
        uvicorn_config_params = {
            "app": self.app,
            "host": self.config.get('host', '127.0.0.1'),
            "port": int(self.config.get('port', 8000)),
            "use_colors": True,
            "reload": False, # `reload=True` non è compatibile con create_task in questo modo
            "loop": loop,
            #'log_level':"trace"
            #'log_config':None
        }
        # Aggiunge i parametri SSL se presenti
        if 'ssl_keyfile' in self.config and 'ssl_certfile' in self.config:
            #await messenger.post(domain='debug', message="SSL abilitato.")
            uvicorn_config_params['ssl_keyfile'] = self.config['ssl_keyfile']
            uvicorn_config_params['ssl_certfile'] = self.config['ssl_certfile']
        else:
            #await messenger.post(domain='debug', message="SSL disabilitato.")
            pass

        # Costruisci la stringa della porta
        port_str = ""
        if 'port' in uvicorn_config_params:
            port_str = f":{uvicorn_config_params['port']}"

        # Costruisci l'URL
        self.url = f"http{'s' if 'ssl_certfile' in self.config else ''}://{uvicorn_config_params['host']}{port_str}"
        try:
            # Crea e avvia il server Uvicorn come task asyncio
            config = Config(**uvicorn_config_params)
            server = Server(config)
            await server.serve()
            #await messenger.post(domain='debug', message=f"Server avviato su {uvicorn_config_params['host']}:{uvicorn_config_params['port']}")
        except Exception as e:
            # Logga errori critici all'avvio del server
            #await messenger.post(domain='error', message=f"Errore critico durante l'avvio del server Uvicorn: {e}")
            pass
        
    async def logout(self,request,defender) -> None:
        assert request.scope.get("app") is not None, "Invalid Starlette app"
        request.session.clear()
        response = RedirectResponse('/', status_code=303)
        response.delete_cookie("session_token")
        return response

    async def login(self, request):
        """Gestisce il login dell'utente con autenticazione basata su IP e sessione."""
        
        client_ip = request.client.host
        session_identifier = request.cookies.get('session_identifier', secrets.token_urlsafe(16))
        url_precedente = request.session.get("url_precedente",request.url)
        
        # Determina le credenziali in base al metodo HTTP
        if request.method == 'GET':
            credentials = dict(request.query_params)
        elif request.method == 'POST':
            credentials = dict(await request.form())
        else:
            return RedirectResponse('/', status_code=405)

        # Autenticazione tramite defender
        session = await self.defender.authenticate(storekeeper,ip=client_ip, identifier=session_identifier, **credentials)
        provider = credentials.get('provider', 'undefined')
        
        # Aggiorna la sessione se l'autenticazione ha avuto successo
        #if session:
        #    request.session.update(session)

        # Crea la risposta di reindirizzamento
        response = RedirectResponse(url_precedente, status_code=303)
        # Imposta i cookie della sessione se non già presenti
        if 'session_identifier' not in request.cookies:
            response.set_cookie(key='session_identifier', value=session_identifier)
        
        #response.set_cookie(key='session', value=token, max_age=3600)
        response.set_cookie(key='session', value=session)
        
        #await messenger.post(domain=f"error.{client_ip}",message=f"🔑 Login completato per IP: {client_ip} | con provider: {provider} | Session: {session_identifier}")

        return response

    async def websocket(self, websocket):
        ip = websocket.client.host
        await websocket.accept()
        #await messenger.post(domain='info', message=f"🔌 Connessione WebSocket da {ip}")

        #ws_queue = asyncio.Queue()  # Coda per i messaggi WebSocket
        #messenger_queue = asyncio.Queue()  # Coda per i messaggi di Messenger
        stop_event = asyncio.Event()  # Evento per fermare il loop quando necessario

        async def listen_websocket():
            try:
                while not stop_event.is_set():
                    msg = await websocket.receive_text()
                    #await messenger.post(domain='debug', message=f"📥 Messaggio dal client: {msg}")
                    await websocket.send_text(msg)
            except Exception:
                stop_event.set()  # Ferma il ciclo se il WebSocket si chiude

        async def listen_for_updates():
            while not stop_event.is_set():
                msg = await messenger.read(domain='*',identity=ip)
                #await messenger.post(domain='debug', message=f"📨 Messaggio dal server: {msg}")
                #await messenger_queue.put(msg)
                await websocket.send_text(msg)
    
    async def websocketssh(self, websocket):
        ip = websocket.client.host

        # Sessione di autenticazione
        session = await self.defender.whoami(ip=ip)
        await websocket.accept()

        try:
            # Riceve parametri iniziali
            initial_message = await websocket.receive_text()
            #await messenger.post(domain='debug', message=f"Sessione {session} con messaggio iniziale: {initial_message}")
            params = json.loads(initial_message)
            username = params.get("username")
            password = params.get("password")
            host = params.get("host")

            # Connessione SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password)
            channel = ssh.invoke_shell()

            # Invia la risposta iniziale del terminale (banner, prompt, ecc.)
            if channel.recv_ready():
                initial_response = channel.recv(1024).decode('utf-8')
                await websocket.send_text(initial_response)

            # Lettura dati da SSH → WebSocket
            async def read_from_channel():
                while True:
                    if websocket.client_state.name != "CONNECTED":
                        break
                    if channel.recv_ready():
                        data = channel.recv(1024).decode('utf-8')
                        await websocket.send_text(data)
                    await asyncio.sleep(0.01)

            # Lettura dati da WebSocket → SSH
            async def read_from_websocket():
                while True:
                    data = await websocket.receive_text()
                    if data:
                        channel.send(data)

            await asyncio.gather(read_from_channel(), read_from_websocket())

        except Exception as e:
            #await self.messenger.post(domain='error', message=f"Errore durante la sessione SSH-WebSocket: {e}")
            pass
        finally:
            try:
                if channel:
                    channel.close()
                if ssh:
                    ssh.close()
                #await self.messenger.post(domain='debug', message=f"Sessione SSH chiusa per {session}")
            except Exception as close_err:
                #await self.messenger.post(domain='error', message=f"Errore durante la chiusura SSH: {close_err}")
                pass
    
    async def action(self, request, storekeeper, messenger, **constants):
        #print(request.cookies.get('user'))
        match request.method:
            case 'GET':
                query = dict(request.query_params)
                #await messenger.post(identifier=id,name=request.url.path[1:],value=dict(query))
                #data = await messenger.get(identifier=id,name=request.url.path[1:],value=dict(query))
                #import application.action.gather as gather
                
                data = await gather.gather(messenger,storekeeper,model=query['model'],payload=query)
                return JSONResponse(data)
                
            case 'POST':
                form = await request.form()
                data = dict(form)
                
                request.scope["user"] = data
                #await messenger.post(name=request.url.path[1:],value={'model':data['model'],'value':data})
                return RedirectResponse('/', status_code=303)

    async def render_view(self,request):
        request.session["url_precedente"] = str(request.url)
        html = await self.mount_view(str(request.url),identifier = request.cookies.get('session_identifier', secrets.token_urlsafe(16)))
        return HTMLResponse(html)

    async def mount_view(self, url,**kargs):
        def process_url(url, default_base_url):
            """
            Unisce raw_url con default_base_url per completare scheme/netloc/etc. usa _replace()
            """
            base = urlparse(default_base_url)
            parsed = urlparse(url)

            merged = parsed._asdict()  # scheme, netloc, path, params, query, fragment
            for field in base._fields:
                if not merged.get(field):          # se vuoto -> copia dal base
                    merged[field] = getattr(base, field)

            return parsed._replace(**merged)
        parsed_url = process_url(url, self.url)   # self.url = base url

        matched_route = None

        for route_path, route_data in self.routes.items():
            # costruiamo il pattern regex in modo sicuro:
            parts = []
            last_idx = 0
            param_names = []

            # trova tutte le {...} nel route_path
            for m in re.finditer(r'\{([^}]+)\}', route_path):
                # escape della parte statica prima della match
                parts.append(re.escape(route_path[last_idx:m.start()]))
                # gruppo di cattura per quel segmento
                parts.append('([^/]+)')
                # salva il nome del parametro, rimuovendo eventuale '$' iniziale
                param_names.append(m.group(1).lstrip('$'))
                last_idx = m.end()

            # aggiungi la parte finale (escaped)
            parts.append(re.escape(route_path[last_idx:]))
            regex_pattern = '^' + ''.join(parts) + '$'

            match = re.search(regex_pattern, parsed_url.path)
            if match:
                matched_route = {
                    'view': route_data.get('view'),
                    'params': {},
                    'layout': route_data.get('layout')
                }

                for i, name in enumerate(param_names):
                    matched_route['params'][name] = match.group(i + 1)

                break  # prima corrispondenza -> esci

        if not matched_route:
            #await messenger.post(domain='debug', message=f"Nessuna rotta corrispondente per l'URL: {url}")
            return None

        # log (opzionale)
        #await messenger.post(domain='debug', message=f"Percorso trovato: {matched_route['view']} per l'URL: {url}")
        #await messenger.post(domain='debug', message=f"Parametri estratti: {matched_route['params']}")

        # parametri query e fragment come dict di liste
        query_params = parse_qs(parsed_url.query, keep_blank_values=True)
        frag_params = parse_qs(parsed_url.fragment, keep_blank_values=True)

        # path come lista di segmenti (evita elemento vuoto se path è '/')
        stripped = parsed_url.path.lstrip('/')
        path_list = stripped.split('/') if stripped else []

        url_payload = {
            'url': self.url,
            'protocol': parsed_url.scheme,
            'host': parsed_url.hostname,
            'port': parsed_url.port,
            'path': path_list,
            'query': query_params,
            'fragment': frag_params
        }

        # chiama il modello / builder come nel tuo flusso
        #url_payload = await language.normalize(url_payload,scheme_url)
        return await self.render_template(file=matched_route['view'], url=url_payload, mode=['main'], identifier=kargs.get('identifier'))

    def mount_route(self, routes):
        for path, data in self.routes.items():
            typee = data.get('type')
            method = data.get('method')
            view = data.get('view')

            # Associa il path alla view (utile per debug o reverse lookup)
            self.views[path] = view

            # Se è una mount statica
            if typee == 'mount' and path == '/static':
                r = Mount(path, app=StaticFiles(directory='/public'), name="static")
                routes.append(r)
                continue

            # Determina l'endpoint
            if typee == 'model':
                endpoint = self.model
            elif typee == 'view':
                endpoint = self.render_view
            elif typee == 'action':
                endpoint = self.action
            elif typee == 'login':
                endpoint = self.login
            elif typee == 'logout':
                endpoint = self.logout
            else:
                endpoint = self.default_handler  # fallback o gestione errori

            # Crea la rotta e aggiungila
            r = Route(path, endpoint=endpoint, methods=[method])
            routes.append(r)

    def mount_css(self, node, context):
        pass

    def node_create(self, tag, attrs={}, inner=[]):
        # Se tag è una funzione (es. un componente funzionale/lambda)
        if callable(tag) and type(tag).__name__ == "function":
            return str(tag({"inner": inner, "attrs": attrs}))
        # Altrimenti trattalo come un elemento htpy standard
        children = [Markup(i) for i in inner] if isinstance(inner, list) else Markup(inner or "")
        if not hasattr(tag, "__getitem__"):
            return str(tag(**attrs))
        return str(tag(**attrs)[children])
    
    def node_union(self, node, context):
        pass
    
    def node_update(self, node, context):
        pass