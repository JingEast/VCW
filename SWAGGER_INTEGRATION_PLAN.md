# SWAGGER_INTEGRATION_PLAN.md

## OpenAPI / Swagger Integration Plan

Generated: 2026-06-03
Target: Auto-generate API docs from Flask route docstrings

---

## 1. Technology Choice

**Library**: `flasgger` (>=0.9.7)

**Reason**:
- Minimal code changes (reads docstrings)
- Compatible with Flask Blueprints
- Supports JWT auth in Swagger UI
- Auto-generates swagger.json

**Alternative**: `flask-restx` — requires class-based resources (high migration cost)

---

## 2. Integration Steps

### Step 1 — Install Dependency

```bash
pip install flasgger>=0.9.7
```

Already added to `requirements.txt`.

### Step 2 — Initialize in app/__init__.py

Add after blueprint registration:

```python
from flasgger import Swagger

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec_1",
            "route": "/apispec_1.json",
            "rule_filter": lambda rule: rule.endpoint.startswith("api_v1"),
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs",
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "VCW API",
        "description": "港籍升学热点文案批量生成器 API",
        "version": "1.0.0",
    },
    "basePath": "/api/v1",
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Token: Bearer <token>",
        }
    },
}

Swagger(app, config=swagger_config, template=swagger_template)
```

### Step 3 — Annotate API Routes

Example for `/api/v1/generate/stream`:

```python
@bp.route("/generate/stream")
def generate_stream():
    """
    Stream LLM generation in real-time.
    ---
    tags:
      - Generation
    security:
      - Bearer: []
    responses:
      200:
        description: SSE stream of generated content
      401:
        description: Unauthorized
    """
```

Example for `/api/v1/generate/async`:

```python
@bp.route("/generate/async", methods=["POST"])
def generate_async():
    """
    Submit async generation job.
    ---
    tags:
      - Generation
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            prompt:
              type: string
            model:
              type: string
    responses:
      202:
        description: Job accepted
        schema:
          type: object
          properties:
            task_id:
              type: string
      401:
        description: Unauthorized
    """
```

### Step 4 — Public Endpoints

Routes to EXCLUDE from auth requirement in Swagger UI:
- `/api/v1/model/status`
- `/health`
- `/metrics`

---

## 3. Directory Structure

```
app/
├── api/
│   └── v1/
│       ├── __init__.py      # Register Swagger on bp
│       ├── generate.py      # Add docstrings
│       ├── editor.py        # Add docstrings
│       ├── prompts.py       # Add docstrings
│       ├── trends.py        # Add docstrings
│       └── misc.py          # Add docstrings
```

---

## 4. Access URLs

After integration:
- Swagger UI: `http://127.0.0.1:5000/apidocs`
- OpenAPI JSON: `http://127.0.0.1:5000/apispec_1.json`

---

## 5. Migration Effort

| Task | Effort | Files Modified |
|------|--------|----------------|
| Install flasgger | 5 min | requirements.txt |
| Init in create_app | 15 min | app/__init__.py |
| Annotate 18 API routes | 2-3 hours | 5 files in app/api/v1/ |
| Test Swagger UI | 30 min | - |
| **Total** | **~4 hours** | **7 files** |

---

## 6. Benefits

- Auto-generated interactive API documentation
- Frontend team can generate TypeScript types from swagger.json
- API consumers can test endpoints directly in browser
- Single source of truth (docstrings == docs)
