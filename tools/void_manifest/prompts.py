"""Prompts for Architectural Graph generation — the Knower's instruction set.

This is the "lens" that transforms unmanifest intent (natural language app
description) into the Conscious Void (structured ArchitecturalGraph JSON).
Designed to work with any capable LLM via OpenAI-compatible API.
"""
from __future__ import annotations

from typing import Dict, Any

# The schema documentation injected into the prompt so the LLM knows
# EXACTLY what to produce. This is the contract.
SCHEMA_DOC = """## Architectural Graph Schema (format_version: "1.0.0")

You must output valid JSON matching this structure:

```json
{
  "format_version": "1.0.0",
  "app": {
    "name": "PascalCaseName",
    "description": "One-line description",
    "stack": "nextjs",
    "port": 3000
  },
  "entities": [
    {
      "name": "PascalCaseName",
      "table": "snake_case_table",
      "fields": [
        {
          "name": "fieldName",
          "type": "string|integer|float|boolean|datetime|text|email|url|json",
          "required": true,
          "unique": false,
          "default": null,
          "description": "What this field stores"
        }
      ],
      "relations": [
        {
          "type": "has_many|belongs_to|has_one|many_to_many",
          "target": "OtherEntityName",
          "foreign_key": "other_entity_id",
          "through": ""
        }
      ],
      "description": "What this entity represents"
    }
  ],
  "routes": [
    {
      "path": "/api/resource",
      "method": "GET|POST|PUT|PATCH|DELETE",
      "description": "What this endpoint does",
      "auth_required": false,
      "roles": [],
      "handler_logic": "Natural language description of handler logic",
      "input_schema": {},
      "output_schema": {},
      "queries_entities": ["EntityName"]
    }
  ],
  "pages": [
    {
      "path": "/route",
      "title": "Page Title",
      "auth_required": false,
      "layout": "default",
      "components": ["ComponentName"],
      "data_routes": ["/api/resource"],
      "description": "What this page does"
    }
  ],
  "components": [
    {
      "name": "ComponentName",
      "type": "card|form|list|modal|nav|layout|page|custom",
      "props": [
        {"name": "propName", "type": "string", "required": true}
      ],
      "state": [
        {"name": "stateVar", "type": "string", "default": null}
      ],
      "children": ["ChildComponentName"],
      "description": "What this component renders and does"
    }
  ],
  "auth": {
    "type": "jwt|session|api_key|none",
    "roles": ["user", "admin"],
    "login_route": "/api/auth/login",
    "register_route": "/api/auth/register",
    "token_field": "Authorization"
  }
}
```

### Critical Rules

1. EVERY entity MUST have an "id" field (string or integer) — the primary key.
2. Every belongs_to relation MUST have the corresponding foreign key as a field.
3. Every component referenced by a page MUST exist in the components array.
4. Every data_route referenced by a page MUST exist in the routes array.
5. Every relation target MUST be an entity that exists.
6. Routes that modify data (POST/PUT/DELETE) should have auth_required: true.
7. Pages that show user data should have auth_required: true.
8. Input/output schemas use JSON Schema format with "type" and "properties".
9. Components of type "page" or "layout" go in pages, not components.
10. The app MUST be internally consistent — no orphan references.

### Pattern Reference

**Common entity patterns:**
- User: id, email, name, password_hash, role, createdAt, updatedAt
- Session: id, userId (belongs_to User), token, expiresAt
- [Resource]: id, name, description, userId (belongs_to User if owned), createdAt

**Common route patterns:**
- GET /api/[resources] → list all (public or auth)
- GET /api/[resources]/:id → get one (public or auth)
- POST /api/[resources] → create (auth required)
- PUT /api/[resources]/:id → update (auth required)
- DELETE /api/[resources]/:id → delete (auth required)

**Common page patterns:**
- / → landing/home page
- /dashboard → authenticated dashboard
- /[resources] → list view
- /[resources]/:id → detail view
- /login → auth page
"""


SYSTEM_PROMPT = f"""You are an expert software architect. Your task is to convert a user's natural language description of a web application into a complete, internally consistent Architectural Graph in JSON format.

The Architectural Graph is a structured specification that fully describes the application. It is the "conscious void" — the complete conception before any code exists. Every entity, every route, every component, every relationship must be specified.

**Your process:**
1. Read the user's description carefully
2. Identify all entities (data models) needed
3. Define all relationships between entities
4. Design all API routes needed
5. Define all pages and their data requirements
6. Define all components and their props/state
7. Ensure internal consistency — every reference must be valid
8. Output ONLY valid JSON — no explanation, no markdown wrapping

{SCHEMA_DOC}

Output ONLY the JSON object. No preamble. No explanation. The JSON must parse."""


def build_messages(app_description: str, context: Dict[str, Any] = None) -> list:
    """Build the messages array for the LLM call.

    Args:
        app_description: Natural language description of the desired app
        context: Optional additional context (stack preferences, existing entities, etc.)

    Returns:
        List of message dicts ready for the LLM API
    """
    user_content = f"""Create a complete Architectural Graph for this application:

{app_description}

{f"Additional context: {context}" if context else ""}

Remember: output ONLY the JSON object. No explanations."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]


REFINE_PROMPT = """The Architectural Graph you produced has the following issues found by the validator (the Witness):

{issues}

Please fix the JSON to resolve ALL of these issues. Output ONLY the corrected JSON object. No explanations."""


def build_refine_messages(graph_json: str, issues: list) -> list:
    """Build messages to ask the LLM to fix validation issues."""
    issue_text = "\n".join(f"- [{i['code']}] {i['message']}" for i in issues)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Create a complete Architectural Graph."},
        {"role": "assistant", "content": graph_json},
        {"role": "user", "content": REFINE_PROMPT.format(issues=issue_text)}
    ]
