from dataclasses import dataclass, field, asdict
from typing     import Optional
import json


@dataclass
class IRProp:
    name:     str
    type:     str          = "any"
    required: bool         = True
    default:  Optional[str] = None


@dataclass
class IRState:
    name:  str
    init:  Optional[str] = None
    type:  str           = "any"


@dataclass
class IRComputed:
    name:       str
    expression: str
    deps:       list[str] = field(default_factory=list)


@dataclass
class IRLifecycle:
    hook: str
    body: str = ""


@dataclass
class IRMethod:
    name:   str
    params: list[str] = field(default_factory=list)
    body:   str       = ""


@dataclass
class IREventBinding:
    event:   str
    handler: str


@dataclass
class IRTemplateNode:
    tag:        str
    attrs:      dict[str, str]        = field(default_factory=dict)
    events:     list[IREventBinding]  = field(default_factory=list)
    children:   list["IRTemplateNode"] = field(default_factory=list)
    text:       Optional[str]         = None
    condition:  Optional[str]         = None
    loop:       Optional[str]         = None
    loop_item:  Optional[str]         = None


@dataclass
class IRImport:
    source:     str
    specifiers: list[str] = field(default_factory=list)
    default:    Optional[str] = None


@dataclass
class IR:
    framework:  str
    component:  str                  = "App"
    props:      list[IRProp]         = field(default_factory=list)
    state:      list[IRState]        = field(default_factory=list)
    computed:   list[IRComputed]     = field(default_factory=list)
    lifecycle:  list[IRLifecycle]    = field(default_factory=list)
    methods:    list[IRMethod]       = field(default_factory=list)
    imports:    list[IRImport]       = field(default_factory=list)
    template:   Optional[IRTemplateNode] = None
    styles:     str                  = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "IR":
        return cls(
            framework = data.get("framework", "unknown"),
            component = data.get("component", "App"),
            props     = [IRProp(**p)      for p in data.get("props",     [])],
            state     = [IRState(**s)     for s in data.get("state",     [])],
            computed  = [IRComputed(**c)  for c in data.get("computed",  [])],
            lifecycle = [IRLifecycle(**l) for l in data.get("lifecycle", [])],
            methods   = [IRMethod(**m)    for m in data.get("methods",   [])],
            imports   = [IRImport(**i)    for i in data.get("imports",   [])],
            template  = None,
            styles    = data.get("styles", ""),
        )
