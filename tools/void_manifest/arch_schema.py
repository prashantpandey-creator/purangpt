"""Architectural Graph Schema — the Conscious Void format.

This schema defines the complete structured representation of a web application.
It is the intermediate stage between unmanifest intent and manifest code — the
"pure thought" that becomes the application. Every aspect of the app is
represented here, typed, with explicit relationships.

The schema is designed so that:
1. An LLM can produce it reliably (closed vocabulary, typed fields)
2. A validator can check it deterministically (the Witness)
3. A renderer can compile it to code mechanically (the Manifest Engine)

Format version: 1.0.0
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal, Union
from dataclasses import dataclass, field
from enum import Enum


# ─── Primitive types ─────────────────────────────────────────────────────────

class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TEXT = "text"
    EMAIL = "email"
    URL = "url"
    JSON = "json"

class RelationType(str, Enum):
    HAS_MANY = "has_many"
    BELONGS_TO = "belongs_to"
    HAS_ONE = "has_one"
    MANY_TO_MANY = "many_to_many"

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

class AuthType(str, Enum):
    JWT = "jwt"
    SESSION = "session"
    API_KEY = "api_key"
    NONE = "none"

class ComponentType(str, Enum):
    PAGE = "page"
    LAYOUT = "layout"
    CARD = "card"
    FORM = "form"
    LIST = "list"
    MODAL = "modal"
    NAV = "nav"
    CUSTOM = "custom"


# ─── Schema definitions ──────────────────────────────────────────────────────

@dataclass
class FieldDef:
    name: str
    type: FieldType
    required: bool = True
    unique: bool = False
    default: Any = None
    description: str = ""

@dataclass
class RelationDef:
    type: RelationType
    target: str                      # Entity name this relation points to
    foreign_key: str = ""            # The field on this/other entity
    through: str = ""                # For many_to_many: the join table

@dataclass
class EntityDef:
    name: str                        # PascalCase, e.g. "User"
    table: str = ""                  # DB table name (defaults to snake_case)
    fields: List[FieldDef] = field(default_factory=list)
    relations: List[RelationDef] = field(default_factory=list)
    description: str = ""

    def __post_init__(self):
        if not self.table:
            self.table = _to_snake(self.name)

@dataclass
class RouteDef:
    path: str                        # e.g. "/api/users"
    method: HttpMethod
    description: str
    auth_required: bool = False
    roles: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    handler_logic: str = ""          # NL description of what the handler does
    queries_entities: List[str] = field(default_factory=list)  # Which entities this touches

@dataclass
class PageDef:
    path: str                        # e.g. "/dashboard"
    title: str
    auth_required: bool = False
    layout: str = "default"
    components: List[str] = field(default_factory=list)      # Component names
    data_routes: List[str] = field(default_factory=list)      # Route paths this page calls
    description: str = ""

@dataclass
class ComponentDef:
    name: str                        # PascalCase, e.g. "ProductCard"
    type: ComponentType = ComponentType.CUSTOM
    props: List[Dict[str, Any]] = field(default_factory=list)
    # props: [{"name": "product", "type": "Product", "required": true}]
    state: List[Dict[str, Any]] = field(default_factory=list)
    # state: [{"name": "isOpen", "type": "boolean", "default": false}]
    children: List[str] = field(default_factory=list)        # Child component names
    description: str = ""

@dataclass
class AuthDef:
    type: AuthType = AuthType.JWT
    roles: List[str] = field(default_factory=list)
    login_route: str = "/api/auth/login"
    register_route: str = "/api/auth/register"
    token_field: str = "Authorization"

@dataclass
class AppDef:
    name: str
    description: str = ""
    stack: Literal["nextjs", "express-react"] = "nextjs"
    port: int = 3000

@dataclass
class ArchitecturalGraph:
    """The Conscious Void — complete structured application specification."""
    app: AppDef
    entities: List[EntityDef] = field(default_factory=list)
    routes: List[RouteDef] = field(default_factory=list)
    pages: List[PageDef] = field(default_factory=list)
    components: List[ComponentDef] = field(default_factory=list)
    auth: AuthDef = field(default_factory=AuthDef)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to the LLM-facing JSON schema format."""
        return _serialize(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchitecturalGraph":
        """Deserialize from LLM output."""
        return _deserialize(d)


# ─── Witness: Validation ─────────────────────────────────────────────────────

def validate(graph: ArchitecturalGraph) -> List[Dict[str, str]]:
    """Witness — validate the Architectural Graph for consistency and completeness.
    Returns a list of issues (empty = clean). Each issue is {code, message}.
    This is the deterministic verification that runs before manifestation.
    """
    issues: List[Dict[str, str]] = []
    entity_names = {e.name for e in graph.entities}
    component_names = {c.name for c in graph.components}
    route_paths = {r.path for r in graph.routes}

    # 1. Every relation target must be a defined entity
    for e in graph.entities:
        for r in e.relations:
            if r.target not in entity_names:
                issues.append({"code": "unknown_relation_target",
                               "message": f"Entity '{e.name}' has relation to unknown '{r.target}'"})

    # 2. Every route's queries_entities must reference real entities
    for r in graph.routes:
        for qe in r.queries_entities:
            if qe not in entity_names:
                issues.append({"code": "unknown_route_entity",
                               "message": f"Route '{r.path}' queries unknown entity '{qe}'"})

    # 3. Every page's components must exist
    for p in graph.pages:
        for c_name in p.components:
            if c_name not in component_names:
                issues.append({"code": "unknown_page_component",
                               "message": f"Page '{p.path}' uses unknown component '{c_name}'"})

    # 4. Every page's data_routes must reference defined routes
    for p in graph.pages:
        for dr in p.data_routes:
            if dr not in route_paths:
                issues.append({"code": "unknown_page_route",
                               "message": f"Page '{p.path}' references unknown route '{dr}'"})

    # 5. Every entity with BELONGS_TO must have a foreign key field
    for e in graph.entities:
        for r in e.relations:
            if r.type == RelationType.BELONGS_TO:
                fk = r.foreign_key or f"{_to_snake(r.target)}_id"
                field_names = {f.name for f in e.fields}
                if fk not in field_names:
                    issues.append({"code": "missing_foreign_key",
                                   "message": f"Entity '{e.name}' has belongs_to {r.target} but missing FK field '{fk}'"})

    # 6. Auth-required routes need auth configured
    if graph.auth.type == AuthType.NONE:
        for r in graph.routes:
            if r.auth_required:
                issues.append({"code": "auth_required_no_auth",
                               "message": f"Route '{r.path}' requires auth but auth type is 'none'"})

    # 7. Component props types should reference known entities if they look like entity names
    for c in graph.components:
        for prop in c.props:
            ptype = str(prop.get("type", ""))
            if ptype in entity_names:
                continue  # Valid entity reference
            # Prop types should be primitives or entity names
            if ptype and ptype[0].isupper() and ptype not in entity_names and ptype not in _PRIMITIVE_TYPES:
                # Might be a missing entity reference — soft warning, not error
                pass  # Allow custom types for flexibility

    return issues


_PRIMITIVE_TYPES = {"string", "number", "boolean", "Date", "any", "void", "ReactNode"}
_CAMEL_TO_SNAKE = {}


def _to_snake(name: str) -> str:
    """PascalCase → snake_case."""
    result = []
    for i, ch in enumerate(name):
        if ch.isupper():
            if i > 0 and name[i-1].islower():
                result.append("_")
            result.append(ch.lower())
        else:
            result.append(ch)
    return "".join(result)


def _to_camel(name: str) -> str:
    """snake_case → camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ─── Serialization ───────────────────────────────────────────────────────────

def _serialize(graph: ArchitecturalGraph) -> Dict[str, Any]:
    """Serialize to JSON-compatible dict (the LLM-facing format)."""
    return {
        "format_version": "1.0.0",
        "app": {
            "name": graph.app.name,
            "description": graph.app.description,
            "stack": graph.app.stack,
            "port": graph.app.port,
        },
        "entities": [
            {
                "name": e.name,
                "table": e.table,
                "fields": [{"name": f.name, "type": f.type.value, "required": f.required,
                           "unique": f.unique, "default": f.default, "description": f.description}
                          for f in e.fields],
                "relations": [{"type": r.type.value, "target": r.target,
                              "foreign_key": r.foreign_key, "through": r.through}
                             for r in e.relations],
                "description": e.description,
            }
            for e in graph.entities
        ],
        "routes": [
            {
                "path": r.path, "method": r.method.value,
                "description": r.description, "auth_required": r.auth_required,
                "roles": r.roles, "handler_logic": r.handler_logic,
                "input_schema": r.input_schema, "output_schema": r.output_schema,
                "queries_entities": r.queries_entities,
            }
            for r in graph.routes
        ],
        "pages": [
            {
                "path": p.path, "title": p.title,
                "auth_required": p.auth_required, "layout": p.layout,
                "components": p.components, "data_routes": p.data_routes,
                "description": p.description,
            }
            for p in graph.pages
        ],
        "components": [
            {
                "name": c.name, "type": c.type.value,
                "props": c.props, "state": c.state,
                "children": c.children, "description": c.description,
            }
            for c in graph.components
        ],
        "auth": {
            "type": graph.auth.type.value,
            "roles": graph.auth.roles,
            "login_route": graph.auth.login_route,
            "register_route": graph.auth.register_route,
            "token_field": graph.auth.token_field,
        },
    }


def _deserialize(d: Dict[str, Any]) -> ArchitecturalGraph:
    """Deserialize from dict (LLM output) to ArchitecturalGraph."""
    app_d = d.get("app", {})
    app = AppDef(
        name=app_d.get("name", "Untitled"),
        description=app_d.get("description", ""),
        stack=app_d.get("stack", "nextjs"),
        port=app_d.get("port", 3000),
    )

    entities = []
    for e in d.get("entities", []):
        fields = [FieldDef(
            name=f["name"], type=FieldType(f["type"]),
            required=f.get("required", True), unique=f.get("unique", False),
            default=f.get("default"), description=f.get("description", "")
        ) for f in e.get("fields", [])]
        relations = [RelationDef(
            type=RelationType(r["type"]), target=r["target"],
            foreign_key=r.get("foreign_key", ""), through=r.get("through", "")
        ) for r in e.get("relations", [])]
        entities.append(EntityDef(
            name=e["name"], table=e.get("table", ""),
            fields=fields, relations=relations,
            description=e.get("description", "")
        ))

    routes = [RouteDef(
        path=r["path"], method=HttpMethod(r["method"]),
        description=r.get("description", ""),
        auth_required=r.get("auth_required", False),
        roles=r.get("roles", []),
        handler_logic=r.get("handler_logic", ""),
        input_schema=r.get("input_schema", {}),
        output_schema=r.get("output_schema", {}),
        queries_entities=r.get("queries_entities", []),
    ) for r in d.get("routes", [])]

    pages = [PageDef(
        path=p["path"], title=p.get("title", ""),
        auth_required=p.get("auth_required", False),
        layout=p.get("layout", "default"),
        components=p.get("components", []),
        data_routes=p.get("data_routes", []),
        description=p.get("description", ""),
    ) for p in d.get("pages", [])]

    components = [ComponentDef(
        name=c["name"], type=ComponentType(c.get("type", "custom")),
        props=c.get("props", []), state=c.get("state", []),
        children=c.get("children", []),
        description=c.get("description", ""),
    ) for c in d.get("components", [])]

    auth_d = d.get("auth", {})
    auth = AuthDef(
        type=AuthType(auth_d.get("type", "jwt")),
        roles=auth_d.get("roles", []),
        login_route=auth_d.get("login_route", "/api/auth/login"),
        register_route=auth_d.get("register_route", "/api/auth/register"),
        token_field=auth_d.get("token_field", "Authorization"),
    )

    return ArchitecturalGraph(
        app=app, entities=entities, routes=routes,
        pages=pages, components=components, auth=auth,
    )
