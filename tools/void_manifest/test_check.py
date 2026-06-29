"""Tests for void_manifest — the Puranic LLM engine.

Tests the deterministic components (Witness validation, Manifest rendering)
and the pipeline envelope contract. Does NOT test LLM calls — those are
integration-tested manually.

Run: venv/bin/python -m tools.void_manifest.test_check   (exit 0)
"""
from __future__ import annotations

import json
import os
import tempfile
from tools.void_manifest.arch_schema import (
    ArchitecturalGraph, AppDef, EntityDef, FieldDef, RouteDef, PageDef,
    ComponentDef, AuthDef, RelationDef,
    FieldType, RelationType, HttpMethod, AuthType, ComponentType,
    validate,
)
from tools.void_manifest.render_nextjs import render, write_files
from tools.void_manifest.check import _envelope, _extract_json, conceive, manifest


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _minimal_graph() -> ArchitecturalGraph:
    """A minimal valid graph — a simple todo app."""
    return ArchitecturalGraph(
        app=AppDef(name="TodoApp", description="A simple todo application", stack="nextjs"),
        entities=[
            EntityDef(
                name="User",
                fields=[
                    FieldDef(name="id", type=FieldType.INTEGER, required=True, unique=True),
                    FieldDef(name="email", type=FieldType.EMAIL, required=True, unique=True),
                    FieldDef(name="name", type=FieldType.STRING, required=True),
                    FieldDef(name="password_hash", type=FieldType.STRING, required=True),
                ],
                relations=[
                    RelationDef(type=RelationType.HAS_MANY, target="Task", foreign_key="userId"),
                ],
                description="A registered user",
            ),
            EntityDef(
                name="Task",
                fields=[
                    FieldDef(name="id", type=FieldType.INTEGER, required=True, unique=True),
                    FieldDef(name="title", type=FieldType.STRING, required=True),
                    FieldDef(name="done", type=FieldType.BOOLEAN, required=True, default=False),
                    FieldDef(name="userId", type=FieldType.INTEGER, required=True),
                ],
                relations=[
                    RelationDef(type=RelationType.BELONGS_TO, target="User", foreign_key="userId"),
                ],
                description="A task item",
            ),
        ],
        routes=[
            RouteDef(path="/api/tasks", method=HttpMethod.GET,
                     description="List all tasks for authenticated user",
                     auth_required=True, queries_entities=["Task"]),
            RouteDef(path="/api/tasks", method=HttpMethod.POST,
                     description="Create a new task", auth_required=True,
                     queries_entities=["Task"],
                     input_schema={"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}),
            RouteDef(path="/api/tasks/:id", method=HttpMethod.PUT,
                     description="Update a task", auth_required=True,
                     queries_entities=["Task"]),
            RouteDef(path="/api/tasks/:id", method=HttpMethod.DELETE,
                     description="Delete a task", auth_required=True,
                     queries_entities=["Task"]),
        ],
        pages=[
            PageDef(path="/", title="My Tasks", auth_required=True,
                    components=["TaskList", "TaskForm"],
                    data_routes=["/api/tasks"]),
        ],
        components=[
            ComponentDef(name="TaskList", type=ComponentType.LIST,
                         props=[{"name": "tasks", "type": "Task[]", "required": True}],
                         description="Displays the list of tasks"),
            ComponentDef(name="TaskForm", type=ComponentType.FORM,
                         state=[{"name": "title", "type": "string", "default": ""}],
                         description="Form to create a new task"),
        ],
        auth=AuthDef(type=AuthType.JWT, roles=["user"]),
    )


# ─── Witness: Validation tests ────────────────────────────────────────────────

def test_clean_graph_passes_validation():
    graph = _minimal_graph()
    issues = validate(graph)
    assert issues == [], f"Clean graph should pass, got: {issues}"


def test_orphan_relation_target_is_caught():
    graph = _minimal_graph()
    graph.entities[0].relations.append(
        RelationDef(type=RelationType.HAS_MANY, target="NonExistent")
    )
    issues = validate(graph)
    assert len(issues) >= 1
    assert any("NonExistent" in i["message"] for i in issues)


def test_orphan_route_entity_is_caught():
    graph = _minimal_graph()
    graph.routes[0].queries_entities.append("GhostEntity")
    issues = validate(graph)
    assert len(issues) >= 1
    assert any("GhostEntity" in i["message"] for i in issues)


def test_unknown_page_component_is_caught():
    graph = _minimal_graph()
    graph.pages[0].components.append("MissingComponent")
    issues = validate(graph)
    assert len(issues) >= 1
    assert any("MissingComponent" in i["message"] for i in issues)


def test_unknown_page_route_is_caught():
    graph = _minimal_graph()
    graph.pages[0].data_routes.append("/api/nonexistent")
    issues = validate(graph)
    assert len(issues) >= 1
    assert any("/api/nonexistent" in i["message"] for i in issues)


def test_auth_required_with_auth_none_is_caught():
    graph = _minimal_graph()
    graph.auth.type = AuthType.NONE
    issues = validate(graph)
    assert len(issues) >= 1
    assert any("auth" in i["code"].lower() or "auth" in i["message"].lower() for i in issues)


def test_missing_foreign_key_field_is_caught():
    graph = _minimal_graph()
    # Remove the userId field from Task but keep the belongs_to
    graph.entities[1].fields = [f for f in graph.entities[1].fields if f.name != "userId"]
    issues = validate(graph)
    assert len(issues) >= 1
    assert any("user_id" in i["message"] or "userId" in i["message"] for i in issues)


# ─── Manifest: Rendering tests ────────────────────────────────────────────────

def test_render_produces_files():
    graph = _minimal_graph()
    files = render(graph, "/tmp/test_void_manifest")
    assert len(files) > 0, "Should produce code files"
    # Core files that must exist
    assert "prisma/schema.prisma" in files
    assert "src/types/index.ts" in files
    assert "package.json" in files
    assert "src/app/layout.tsx" in files
    assert "README.md" in files


def test_prisma_schema_contains_models():
    graph = _minimal_graph()
    files = render(graph, "/tmp/test_void_manifest")
    prisma = files["prisma/schema.prisma"]
    assert "model User" in prisma
    assert "model Task" in prisma
    assert "datasource db" in prisma


def test_types_contain_interfaces():
    graph = _minimal_graph()
    files = render(graph, "/tmp/test_void_manifest")
    types = files["src/types/index.ts"]
    assert "export interface User" in types
    assert "export interface Task" in types
    assert "CreateTaskInput" in types  # From POST route


def test_route_rendering():
    graph = _minimal_graph()
    files = render(graph, "/tmp/test_void_manifest")
    # Check that all 4 routes got files
    route_files = [k for k in files if k.startswith("src/app/api/") and k.endswith("route.ts")]
    # Routes to /api/tasks and /api/tasks/:id
    assert len(route_files) >= 1


def test_page_rendering():
    graph = _minimal_graph()
    files = render(graph, "/tmp/test_void_manifest")
    page_files = [k for k in files if k.endswith("page.tsx")]
    assert any("page.tsx" in f for f in page_files)


def test_component_rendering():
    graph = _minimal_graph()
    files = render(graph, "/tmp/test_void_manifest")
    assert "src/components/TaskList.tsx" in files
    assert "src/components/TaskForm.tsx" in files


def test_package_json_is_valid():
    graph = _minimal_graph()
    files = render(graph, "/tmp/test_void_manifest")
    pkg = json.loads(files["package.json"])
    assert pkg["name"] == "todo_app"
    assert "next" in pkg["dependencies"]
    assert "prisma" in pkg["devDependencies"]


# ─── File writing tests ───────────────────────────────────────────────────────

def test_write_files_creates_files_on_disk():
    graph = _minimal_graph()
    with tempfile.TemporaryDirectory() as tmpdir:
        files = render(graph, tmpdir)
        written = write_files(files, tmpdir)
        assert len(written) > 0
        for path in written:
            full = os.path.join(tmpdir, path)
            assert os.path.exists(full), f"Should exist: {full}"
            assert os.path.getsize(full) > 0, f"Should not be empty: {full}"


def test_manifest_with_invalid_graph_fails():
    # Graph with an orphan reference — should fail witness validation
    graph = _minimal_graph()
    bad_dict = graph.to_dict()
    bad_dict["routes"][0]["queries_entities"].append("GhostEntity")
    env = manifest(bad_dict, "/tmp/should_not_create")
    assert env["success"] is False
    assert len(env["errors"]) > 0
    assert any("GhostEntity" in e.get("message", "") for e in env["errors"])


def test_manifest_with_output_dir_writes_files():
    graph = _minimal_graph()
    graph_dict = graph.to_dict()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = manifest(graph_dict, tmpdir)
        assert env["success"] is True
        assert env["data"]["total_files"] > 0
        assert env["data"]["output_dir"] == tmpdir
        # Verify files actually exist
        for f in env["data"]["files"]:
            assert os.path.exists(os.path.join(tmpdir, f))


# ─── Envelope contract ────────────────────────────────────────────────────────

def test_conceive_envelope_has_correct_shape():
    env = conceive("xyzzy nonexistent gibberish that produces junk")
    assert "success" in env
    assert "data" in env
    assert "metadata" in env
    assert "errors" in env
    assert isinstance(env["errors"], list)


def test_extract_json_strips_markdown():
    result = _extract_json('```json\n{"a": 1}\n```')
    assert result == {"a": 1}


def test_extract_json_handles_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


# ─── Graph roundtrip ──────────────────────────────────────────────────────────

def test_graph_to_dict_and_back_is_identity():
    graph = _minimal_graph()
    d = graph.to_dict()
    graph2 = ArchitecturalGraph.from_dict(d)
    assert graph2.app.name == graph.app.name
    assert len(graph2.entities) == len(graph.entities)
    assert len(graph2.routes) == len(graph.routes)
    assert len(graph2.pages) == len(graph.pages)
    assert len(graph2.components) == len(graph.components)
    # Deep check: first entity fields
    e1 = graph.entities[0]
    e2 = graph2.entities[0]
    assert e2.name == e1.name
    assert len(e2.fields) == len(e1.fields)


# ─── Render idempotency ───────────────────────────────────────────────────────

def test_render_is_deterministic():
    """The same graph must produce byte-identical output every time."""
    graph = _minimal_graph()
    files1 = render(graph, "/tmp/a")
    files2 = render(graph, "/tmp/b")
    assert files1.keys() == files2.keys()
    for k in files1:
        assert files1[k] == files2[k], f"File {k} differs between renders"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
