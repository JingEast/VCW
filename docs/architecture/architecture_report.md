# VCW Project Architecture Report

> Generated: 2026-05-31
> Analyzer: Python Architecture Scanner (Enhanced)

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total Python Files | 85 |
| Total Python LOC | 12,460 |
| Config Files (JSON/INI) | 2 |
| Circular Dependencies | 0 |
| Files > 1000 Lines | 0 |
| Max File Size | 771 lines (`vcw_copywriter/prompts/defaults.py`) |

### Architecture Layers

```
┌─────────────────────────────────────────┐
│  tests/        Integration & Unit Tests │
├─────────────────────────────────────────┤
│  app/          Flask Web / API Layer    │
│  ├── pages/       Blueprint views       │
│  ├── api/v1/      REST API endpoints    │
│  ├── services/    Business services     │
│  └── core/        DI container, logging │
├─────────────────────────────────────────┤
│  vcw_copywriter/  Core Business Engine  │
│  ├── prompts/     Prompt system         │
│  ├── scraper/     Web scraping          │
│  ├── db/          SQLAlchemy ORM        │
│  └── *.py         Generators, analyzers │
├─────────────────────────────────────────┤
│  alembic/      Database migrations      │
└─────────────────────────────────────────┘
```

**Dependency Direction**: `app/` → `vcw_copywriter/` → `db/`

---

## 2. Directory Tree

```
VCW/
├── alembic/
│   ├── versions/
│   │   ├── 5ee13a0f45ba_initial_migration.py
│   │   └── 7410015efd2f_add_prompt_versions_table.py
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── __init__.py          (empty, unused)
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── common.py
│   │   │   ├── editor.py
│   │   │   ├── generate.py
│   │   │   ├── misc.py
│   │   │   ├── prompts.py
│   │   │   └── trends.py
│   │   └── __init__.py
│   ├── core/
│   │   ├── __init__.py              (empty)
│   │   ├── container.py             (dependency-injector)
│   │   ├── extensions.py            (empty)
│   │   └── logging_config.py
│   ├── pages/
│   │   ├── __init__.py              (empty)
│   │   ├── batch.py
│   │   ├── config.py
│   │   ├── editor.py
│   │   ├── history.py
│   │   ├── main.py
│   │   ├── memory.py
│   │   ├── prompts.py
│   │   ├── resources.py
│   │   └── trends.py
│   ├── services/
│   │   ├── __init__.py              (empty)
│   │   ├── app_services.py          (legacy DI registration)
│   │   └── prompt_service.py
│   ├── __init__.py                  (Flask app factory, 243 lines)
│   └── container.py                 (legacy custom DI, 138 lines)
├── docs/
│   └── architecture/                (this report)
├── static/
│   ├── css/
│   ├── js/
│   └── logo.jpg
├── templates/
│   ├── base.html
│   ├── batch.html
│   ├── config.html
│   ├── editor.html
│   ├── history.html
│   ├── index.html
│   ├── memory.html
│   ├── prompts.html
│   ├── resources.html
│   ├── result.html
│   └── trends.html
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_errors.py
│   ├── test_generate.py
│   ├── test_routes.py
│   └── test_service.py
├── vcw_copywriter/
│   ├── db/
│   │   ├── repositories/
│   │   │   ├── __init__.py          (empty)
│   │   │   ├── base.py
│   │   │   ├── job_repository.py
│   │   │   ├── memory_repository.py
│   │   │   ├── result_repository.py
│   │   │   └── trend_repository.py
│   │   ├── __init__.py              (empty)
│   │   ├── models.py
│   │   └── session.py
│   ├── prompts/
│   │   ├── templates/
│   │   │   ├── samples/
│   │   │   ├── scenes/
│   │   │   ├── sections/
│   │   │   ├── styles/
│   │   │   └── system/
│   │   ├── __init__.py
│   │   ├── composer.py
│   │   ├── defaults.py              (771 lines, largest)
│   │   ├── loader.py
│   │   ├── registry.py
│   │   └── schemas.py
│   ├── scraper/
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── baidu_hot_provider.py
│   │   │   ├── google_news_provider.py
│   │   │   ├── html_provider.py
│   │   │   ├── playwright_provider.py
│   │   │   └── rss_provider.py
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── config.py                (110 lines, keyword pools)
│   │   ├── pipelines.py
│   │   └── utils.py
│   ├── __init__.py                  (empty)
│   ├── auto_prompt.py
│   ├── batch_generator.py
│   ├── checker.py
│   ├── config.py
│   ├── editor.py
│   ├── generator.py
│   ├── knowledge_base.py
│   ├── light_vector_search.py
│   ├── main.py                      (CLI entry)
│   ├── memory.py
│   ├── model_router.py
│   ├── prompt_builder.py
│   ├── scheduler.py
│   ├── task_queue.py
│   ├── trend_db.py
│   ├── trend_scraper.py
│   └── viral_analyzer.py
├── alembic.ini
├── wsgi.py                          (Web entry, ✅ naming conflict resolved)
├── ARCHITECTURE.md
├── config.json                      (runtime config)
├── generated_prompt.md
├── migrate_from_json.py
├── prompt.txt
├── README.md
├── requirements.txt
├── run.py                           (CLI entry)
├── test_categories.txt
└── 鹿鸣教育logo.JPG
```

---

## 3. Module Dependency Analysis

### 3.1 Top-Level Package Dependencies

| Package | Imports From |
|---------|-------------|
| `alembic` | `vcw_copywriter` |
| `app` | `vcw_copywriter` |
| `migrate_from_json` | `vcw_copywriter` |
| `run` | `vcw_copywriter` |
| `tests` | `app`, `vcw_copywriter` |

**Observation**: The dependency graph is strictly acyclic at the package level.
All UI and orchestration layers (`app/`, `tests/`, `run.py`) depend on the core engine (`vcw_copywriter/`), and never the reverse.

### 3.2 Subsystem Dependency Graph (Mermaid)

```mermaid
flowchart TD
    A[app/pages] --> C[app/core/container]
    B[app/api/v1] --> C
    B --> S[app/services]
    C --> V[vcw_copywriter/*]
    S --> V
    T[tests] --> A
    T --> B
    T --> V
    R[run.py] --> VM[vcw_copywriter.main]
    M[migrate_from_json] --> DB[vcw_copywriter.db]
    AL[alembic] --> DB
```

### 3.3 Detailed Module Import Map

| Module | Imports |
|--------|---------|
| `alembic.env` | `vcw_copywriter.db.models`, `vcw_copywriter.db.session` |
| `app.api.v1.editor` | `app.api.v1.common`, `app.core.container`, `vcw_copywriter.generator` |
| `app.api.v1.generate` | `app.api.v1.common`, `app.core.container`, `app.services.prompt_service`, `vcw_copywriter.checker`, `vcw_copywriter.generator`, `vcw_copywriter.model_router`, `vcw_copywriter.task_queue` |
| `app.api.v1.misc` | `app.api.v1.common`, `app.core.container`, `app.services.prompt_service`, `vcw_copywriter.model_router` |
| `app.api.v1.prompts` | `app.api.v1.common`, `app.core.container`, `vcw_copywriter.knowledge_base`, `vcw_copywriter.prompt_builder` |
| `app.api.v1.trends` | `app.api.v1.common`, `app.core.container` |
| `app.core.container` | `vcw_copywriter.config`, `vcw_copywriter.editor`, `vcw_copywriter.memory`, `vcw_copywriter.scheduler`, `vcw_copywriter.trend_db`, `vcw_copywriter.viral_analyzer` |
| `app.pages.batch` | `app.core.container`, `vcw_copywriter.batch_generator`, `vcw_copywriter.prompt_builder` |
| `app.pages.config` | `app.core.container` |
| `app.pages.editor` | `app.core.container` |
| `app.pages.history` | `app.core.container` |
| `app.pages.main` | `app.core.container`, `vcw_copywriter.checker`, `vcw_copywriter.generator`, `vcw_copywriter.prompt_builder` |
| `app.pages.memory` | `app.core.container` |
| `app.pages.prompts` | `vcw_copywriter.prompt_builder` |
| `app.pages.resources` | `vcw_copywriter.knowledge_base` |
| `app.pages.trends` | `app.core.container`, `vcw_copywriter.auto_prompt`, `vcw_copywriter.trend_scraper` |
| `app.services.app_services` | `app.container`, `vcw_copywriter.config`, `vcw_copywriter.editor`, `vcw_copywriter.memory`, `vcw_copywriter.scheduler`, `vcw_copywriter.trend_db`, `vcw_copywriter.viral_analyzer` |
| `app.services.prompt_service` | `app.core.container`, `vcw_copywriter.prompt_builder` |
| `migrate_from_json` | `vcw_copywriter.db.models`, `vcw_copywriter.db.repositories.memory_repository`, `vcw_copywriter.db.repositories.trend_repository`, `vcw_copywriter.db.session` |
| `run` | `vcw_copywriter.main` |
| `tests.conftest` | `app`, `app.core.container`, `vcw_copywriter.db.session` |
| `tests.test_generate` | `app.pages.main`, `vcw_copywriter.editor`, `vcw_copywriter.generator` |
| `tests.test_service` | `vcw_copywriter.editor` |

---

## 4. Circular Dependencies

✅ **No circular dependencies detected at module level.**

### Manual Verification of Deep Import Chains

The following chains were inspected for potential runtime cycles:

```
app.core.container
  → vcw_copywriter.memory
    → vcw_copywriter.db.session
      → vcw_copywriter.db.models
        → vcw_copywriter.scraper.utils     (leaf, no internal deps)
```

```
vcw_copywriter.main
  → vcw_copywriter.config, .memory, .prompt_builder, .generator, .checker
    → ... (all forward-pointing)
```

**Conclusion**: All import edges point from upper layers to lower layers. No back-edges exist.

---

## 5. Large File Analysis

**No Python files exceed 1000 lines.**

### Top 20 Largest Files

| Rank | Lines | File | Note |
|------|-------|------|------|
| 1 | 771 | `vcw_copywriter/prompts/defaults.py` | Large prompt template constants |
| 2 | 532 | `vcw_copywriter/trend_db.py` | Trend database + scoring logic |
| 3 | 526 | `vcw_copywriter/scraper/providers/html_provider.py` | HTML scraping provider |
| 4 | 419 | `vcw_copywriter/scraper/utils.py` | Scraping utilities |
| 5 | 411 | `vcw_copywriter/auto_prompt.py` | Auto-prompt generation |
| 6 | 409 | `vcw_copywriter/prompts/composer.py` | Prompt composition engine |
| 7 | 337 | `vcw_copywriter/knowledge_base.py` | Knowledge base management |
| 8 | 329 | `vcw_copywriter/scraper/pipelines.py` | Scraping pipelines |
| 9 | 320 | `vcw_copywriter/db/repositories/trend_repository.py` | Trend repo operations |
| 10 | 302 | `vcw_copywriter/model_router.py` | LLM model routing |
| 11 | 277 | `vcw_copywriter/main.py` | CLI main entry |
| 12 | 253 | `vcw_copywriter/db/models.py` | SQLAlchemy models |
| 13 | 243 | `vcw_copywriter/viral_analyzer.py` | Viral content analyzer |
| 14 | 243 | `app/__init__.py` | Flask app factory |
| 15 | 233 | `vcw_copywriter/prompts/loader.py` | Prompt template loader |
| 16 | 224 | `vcw_copywriter/scraper/providers/rss_provider.py` | RSS scraping provider |
| 17 | 214 | `vcw_copywriter/memory.py` | Memory bank implementation |
| 18 | 213 | `tests/test_service.py` | Service tests |
| 19 | 212 | `vcw_copywriter/generator.py` | Copywriter generator |
| 20 | 209 | `vcw_copywriter/checker.py` | Content quality checker |

---

## 6. Configuration Duplication Analysis

### Analyzed Config Files

| File | Type | Purpose |
|------|------|---------|
| `config.json` | JSON | Runtime LLM / memory / output config |
| `alembic.ini` | INI | Alembic migration & logging settings |

### Duplicate Keys

No duplicate keys detected across configuration files.

### Duplicate Values

No duplicate values detected across configuration files.

### ⚠️ Configuration Inconsistency Detected

| Config | Default Database URL | Notes |
|--------|---------------------|-------|
| `alembic.ini` (line 87) | `postgresql://user:pass@localhost/vcw` | Hard-coded placeholder |
| `vcw_copywriter/db/session.py` (line 11) | `sqlite:///data/vcw.db` | Development default |

**Risk**: `alembic.ini` contains a PostgreSQL placeholder that does not match the application's SQLite default. If a developer runs `alembic upgrade head` without setting `DATABASE_URL`, it will attempt to connect to a non-existent PostgreSQL server instead of the project's SQLite file.

**Recommendation**: Align `alembic.ini` with the application's default or document the environment variable requirement prominently.

---

## 7. Key Architecture Findings

### 7.1 Naming Conflict: `app.py` vs `app/` Package ✅ FIXED

**Issue**: The repository contains both `wsgi.py` (top-level entry script, renamed from `app.py`) and `app/` (Python package directory). In Python's import system, when `app.py` is on `sys.path`, `import app` resolves to the **file** `app.py`, not the **package** `app/`.

**Current Mitigation**: `app.py` inserts the project root into `sys.path` before importing:
```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app
```

**Residual Risk**:
- IDEs and static analysis tools may resolve `import app` incorrectly.
- Running `python app.py` from inside the `vcw_copywriter/` or `tests/` directory could fail.
- Circular shadowing if another module tries `import app` before `sys.path` is modified.

**Recommendation**: Rename `app.py` to `wsgi.py`, `web_entry.py`, or `start_web.py` to eliminate the shadowing.

### 7.2 Dual DI Container Implementations ⚠️ HIGH

The project maintains **two parallel dependency-injection containers** with overlapping service registrations:

| File | Framework | Lines | Used By |
|------|-----------|-------|---------|
| `app/container.py` | Custom lightweight DI | 138 | `app.services.app_services` |
| `app/core/container.py` | `dependency-injector` library | 172 | `app.pages.*`, `app.api.v1.*` |

**Behavioral Split**:
- `app/core/container.py` (`AppContainer`) is initialized in `app/__init__.py` (`create_app`) and attached to the Flask app.
- `app.services.app_services` imports from `app.container` (the custom one) and registers identical services into it.
- Most views call `get_service("config")` which reads from `AppContainer`, **not** from the custom container populated by `app_services`.

**Risk**: Services registered in `app_services.py` are effectively orphaned; no production code path consumes them. This creates confusion for new developers about which container is authoritative.

### 7.3 Duplicate Factory Logic ⚠️ MEDIUM

The following factory functions are duplicated with near-identical implementations:

| Function | `app/core/container.py` | `app/services/app_services.py` |
|----------|------------------------|-------------------------------|
| `_make_config` | lines 28–48 | lines 34–52 |
| `_make_memory_bank` | lines 51–56 | lines 57–60 |
| `_make_trend_db` | lines 59–63 | lines 65–66 |
| `_make_editor` | lines 66–70 | lines 71–72 |
| `_make_scheduler` | lines 73–77 | line 77 (direct reference) |
| `_make_viral_analyzer` | lines 80–84 | line 80 (direct reference) |

Both sets construct the same service instances with the same environment-variable override logic (`VCW_API_KEY`, `VCW_BASE_URL`, `VCW_MODEL`).

**Recommendation**: Extract shared factories into `app/core/factories.py` and import them from both the `AppContainer` and any legacy setup code.

### 7.4 Unused / Legacy Files

| File | Status | Recommendation |
|------|--------|---------------|
| `app/container.py` | Legacy custom DI; superseded by `app/core/container.py` | Deprecate and remove after migrating `app_services.py` |
| `app/api/routes/__init__.py` | Empty; actual routes live in `app/api/v1/` | Remove directory or add re-exports |
| `app/core/extensions.py` | Empty | Remove or populate with Flask extensions |
| `app/core/__init__.py` | Empty | Keep for package marker |
| `app/pages/__init__.py` | Empty | Keep for package marker |
| `app/services/__init__.py` | Empty | Keep for package marker |
| `vcw_copywriter/db/__init__.py` | Empty | Keep for package marker |
| `vcw_copywriter/db/repositories/__init__.py` | Empty | Keep for package marker |

### 7.5 Secret Exposure in Config

`config.json` contains a hard-coded API key (`sk-cx09GmOVRbPYYAUnbdm5erh6bOh815zSd3PGV50d5c28UEV0`). While this file is already tracked in the repository, be aware that rotating this key and moving it to environment variables is a security best practice.

---

## 8. Recommendations

1. **Resolve Naming Conflict**: `app.py` → `wsgi.py` (completed) (or similar) to eliminate the `app` module shadowing the `app` package.
2. **Consolidate DI Containers**: Remove `app/container.py` and migrate `app/services/app_services.py` to use `app.core.container.AppContainer` exclusively. Delete `app_services.py` if its registration logic is fully redundant with `AppContainer`.
3. **Eliminate Duplicate Factories**: Extract `_make_*` functions into `app/core/factories.py` and import them into `app/core/container.py`.
4. **Align Alembic Config**: Update `alembic.ini` to default to `sqlite:///data/vcw.db` or add a clear comment that `DATABASE_URL` must be set.
5. **Modularization**: `vcw_copywriter/prompts/defaults.py` (771 lines) is the largest file. Consider splitting prompt templates into individual `.md` files under `vcw_copywriter/prompts/templates/` and loading them dynamically.
6. **Dependency Direction**: The current direction (`app/` → `vcw_copywriter/`) is healthy. Maintain this and avoid introducing reverse dependencies (e.g., `vcw_copywriter/` should never import `app`).
7. **Configuration Security**: Move the LLM API key from `config.json` to an environment variable and load it in `_make_config()`.

---

## 9. Appendix: Raw Data Files

The following files were generated alongside this report and are available in `docs/architecture/`:

| File | Description |
|------|-------------|
| `directory_tree.txt` | Full textual directory tree |
| `module_dependencies.json` | Module → [imported modules] mapping |
| `subpackage_dependencies.json` | Package → [imported packages] mapping |
| `detailed_imports.json` | Per-file absolute & relative import lists |
| `circular_dependencies.txt` | Cycle detection results |
| `large_files.txt` | Files > 1000 lines and top 15 largest |
| `duplicate_configs.txt` | Duplicate key/value analysis across JSON configs |

---

*End of Report*
