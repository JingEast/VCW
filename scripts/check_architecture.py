#!/usr/bin/env python3
"""Architecture validation script for VCW project.

Checks:
  - Circular imports at package/module level
  - Layering violations (forbidden cross-layer dependencies)
  - Infrastructure leakage in domain/interface layers
"""

from __future__ import annotations

import ast
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
EXCLUDE_DIRS = {
    ".venv", "__pycache__", ".git", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "data", "logs",
}

# Dependency rules: layer -> layers it is ALLOWED to import from
LAYER_RULES: dict[str, list[str]] = {
    "interfaces": [],
    "domains": ["interfaces"],
    "clients": ["interfaces"],
    "services": ["interfaces", "domains", "clients", "llm", "prompt_runtime", "vcw_copywriter"],
    "app": ["services", "interfaces", "domains", "clients", "llm", "prompt_runtime", "vcw_copywriter", "app"],
    "llm": ["interfaces"],
    "prompt_runtime": ["interfaces", "llm"],
    "vcw_copywriter": ["vcw_copywriter", "llm", "prompt_runtime"],
    "vcw_celery_tasks": ["services", "interfaces", "vcw_copywriter", "app"],
    "infrastructure": ["domains", "vcw_copywriter"],
    "alembic": ["vcw_copywriter"],
    "tests": [
        "app", "services", "interfaces", "domains", "clients",
        "llm", "prompt_runtime", "vcw_copywriter", "vcw_celery_tasks",
    ],
}

# Infrastructure packages that should not appear in domain/interface layers
INFRA_PACKAGES = {
    "flask", "sqlalchemy", "celery", "httpx", "werkzeug",
    "jinja2", "dependency_injector", "playwright",
}

# Project-level packages
PROJECT_PACKAGES = set(LAYER_RULES.keys()) | {"tests", "alembic", "infrastructure"}


def get_layer(fpath: Path) -> str | None:
    """Determine which architectural layer a file belongs to."""
    rel = fpath.relative_to(PROJECT_ROOT)
    parts = rel.parts
    first = parts[0] if parts else ""
    if first in PROJECT_PACKAGES:
        # Infrastructure subdirectories within domains are treated as infrastructure
        if first == "domains" and len(parts) >= 3 and parts[2] == "infrastructure":
            return "infrastructure"
        return first
    return None


def parse_module_level_imports(fpath: Path) -> list[tuple[str, str]]:
    """Return list of (import_type, module_name) for module-level imports only.

    Imports inside function/method bodies are ignored to avoid flagging
    local imports used for breaking circular dependencies.
    """
    results: list[tuple[str, str]] = []
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return results

    def _is_module_level(node: ast.AST) -> bool:
        """Check if an import node is at module level (not inside a function/class)."""
        for parent in ast.walk(tree):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for child in ast.walk(parent):
                    if child is node:
                        return False
        return True

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            if _is_module_level(node):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    results.append(("import", mod))
        elif isinstance(node, ast.ImportFrom):
            if _is_module_level(node) and node.module:
                mod = node.module.split(".")[0]
                results.append(("from", mod))
    return results


def check_layering() -> dict:
    """Scan all Python files for layering violations and infra leakage."""
    violations = []
    infra_leaks = []
    all_edges: dict[str, set[str]] = defaultdict(set)

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            layer = get_layer(fpath)
            if not layer:
                continue

            for imp_type, mod in parse_module_level_imports(fpath):
                if mod in PROJECT_PACKAGES and mod != layer:
                    all_edges[layer].add(mod)
                    allowed = LAYER_RULES.get(layer, [])
                    if mod not in allowed:
                        rel = fpath.relative_to(PROJECT_ROOT)
                        violations.append({
                            "file": str(rel).replace("\\", "/"),
                            "layer": layer,
                            "violates": mod,
                            "import": f"{imp_type} {mod}",
                        })
                if mod in INFRA_PACKAGES:
                    if layer in ("interfaces", "domains"):
                        rel = fpath.relative_to(PROJECT_ROOT)
                        infra_leaks.append({
                            "file": str(rel).replace("\\", "/"),
                            "layer": layer,
                            "package": mod,
                        })

    return {
        "violations": violations,
        "infra_leaks": infra_leaks,
        "edges": {k: sorted(v) for k, v in all_edges.items()},
    }


def detect_cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    """Detect circular dependencies between layers using DFS."""
    visited = set()
    rec_stack = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in edges.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
        rec_stack.remove(node)

    for node in list(edges.keys()):
        if node not in visited:
            dfs(node, [node])

    # Deduplicate cycles
    unique = []
    seen = set()
    for c in cycles:
        key = tuple(sorted(set(c)))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def main() -> int:
    results = check_layering()
    cycles = detect_cycles(results["edges"])

    print("=" * 60)
    print("VCW Architecture Validation Report")
    print("=" * 60)

    print("\n--- Layer Dependency Graph ---")
    for layer, deps in sorted(results["edges"].items()):
        print(f"  {layer} -> {deps}")

    print("\n--- Circular Dependencies ---")
    if cycles:
        for c in cycles:
            print(f"  CYCLE: {' -> '.join(c)}")
    else:
        print("  None detected")

    print("\n--- Layering Violations ---")
    if results["violations"]:
        for v in results["violations"]:
            print(f"  [{v['layer']}] {v['file']} imports [{v['violates']}] ({v['import']})")
    else:
        print("  None detected")

    print("\n--- Infrastructure Leakage ---")
    if results["infra_leaks"]:
        for v in results["infra_leaks"]:
            print(f"  [{v['layer']}] {v['file']} imports {v['package']}")
    else:
        print("  None detected")

    # Write JSON report
    report_path = PROJECT_ROOT / "docs" / "architecture" / "validation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "edges": results["edges"],
                "cycles": cycles,
                "violations": results["violations"],
                "infra_leaks": results["infra_leaks"],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nReport written to: {report_path}")

    exit_code = 0
    if cycles:
        exit_code |= 1
    if results["violations"]:
        exit_code |= 2
    if results["infra_leaks"]:
        exit_code |= 4
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
