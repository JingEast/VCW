#!/usr/bin/env python3
"""
VCW Project Architecture Analyzer
Generates comprehensive architecture reports.
"""

import ast
import json
import os
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(".").resolve()
OUTPUT_DIR = Path("docs/architecture")

EXCLUDE_DIRS = {
    '.venv', '__pycache__', '.pytest_cache', '.idea', '.git',
    'node_modules', 'data', 'logs'
}


def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def get_all_files():
    files = []
    for root, dirs, filenames in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        # Modify dirs in-place to prevent walking into excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in filenames:
            fpath = root_path / fname
            files.append(fpath)
    return sorted(files)


def generate_directory_tree():
    """Generate a clean directory tree string."""
    lines = ["VCW/"]

    def tree_dir(path: Path, prefix: str = ""):
        try:
            entries = []
            for entry in sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
                if should_exclude(entry):
                    continue
                entries.append(entry)
        except PermissionError:
            return

        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            name = entry.name + ("/" if entry.is_dir() else "")
            lines.append(f"{prefix}{connector}{name}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                tree_dir(entry, prefix + extension)

    tree_dir(PROJECT_ROOT, "")
    return "\n".join(lines)


def parse_imports(file_path: Path):
    abs_imports = []
    rel_imports = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return abs_imports, rel_imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                abs_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level
            if level > 0:
                rel_imports.append(f"{'.' * level}{module}")
            else:
                abs_imports.append(module)
    return abs_imports, rel_imports


def analyze_dependencies(files):
    py_files = [f for f in files if f.suffix == '.py']

    project_modules = set()
    for f in py_files:
        rel = f.relative_to(PROJECT_ROOT)
        module_name = str(rel.with_suffix('')).replace(os.sep, '.')
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]
        project_modules.add(module_name)

    module_imports = defaultdict(list)
    detailed = {}

    for f in py_files:
        rel = f.relative_to(PROJECT_ROOT)
        module_name = str(rel.with_suffix('')).replace(os.sep, '.')
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]

        abs_imp, rel_imp = parse_imports(f)
        detailed[str(rel).replace(os.sep, '/')] = {
            "absolute": abs_imp,
            "relative": rel_imp
        }

        for imp in abs_imp:
            parts = imp.split('.')
            for i in range(len(parts), 0, -1):
                prefix = '.'.join(parts[:i])
                if prefix in project_modules:
                    # Skip self-references and parent-child imports within same package
                    if prefix == module_name:
                        continue
                    if prefix.startswith(module_name + '.') or module_name.startswith(prefix + '.'):
                        continue
                    module_imports[module_name].append(prefix)
                    break

    subpackage_deps = defaultdict(set)
    for mod, deps in module_imports.items():
        mod_pkg = mod.split('.')[0]
        for d in deps:
            dep_pkg = d.split('.')[0]
            if mod_pkg != dep_pkg:
                subpackage_deps[mod_pkg].add(dep_pkg)

    return {
        "module_imports": {k: sorted(set(v)) for k, v in module_imports.items()},
        "subpackage_dependencies": {k: sorted(v) for k, v in subpackage_deps.items()},
        "detailed_imports": detailed
    }


def find_cycles(graph):
    """Find all elementary cycles using Johnson's algorithm simplified."""
    # Build adjacency list
    adj = defaultdict(set)
    all_nodes = set(graph.keys())
    for deps in graph.values():
        all_nodes.update(deps)
    for node in all_nodes:
        if node not in adj:
            adj[node] = set()
    for node, deps in graph.items():
        adj[node].update(deps)

    # Find SCCs, then cycles within each SCC
    index_counter = [0]
    stack = []
    lowlinks = {}
    index = {}
    on_stack = {}
    sccs = []

    def strongconnect(v):
        index[v] = index_counter[0]
        lowlinks[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True

        for w in adj[v]:
            if w not in index:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif on_stack.get(w, False):
                lowlinks[v] = min(lowlinks[v], index[w])

        if lowlinks[v] == index[v]:
            scc = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            sccs.append(scc)

    for v in sorted(all_nodes):
        if v not in index:
            strongconnect(v)

    cycles = []
    for scc in sccs:
        if len(scc) < 2:
            # Check self-loop
            if len(scc) == 1:
                node = scc[0]
                if node in adj[node]:
                    cycles.append([node])
            continue

        # Find cycles in this SCC using DFS
        scc_set = set(scc)
        scc_adj = {n: [d for d in adj[n] if d in scc_set] for n in scc}

        visited = set()
        rec_stack = set()
        path = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in scc_adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    # Normalize
                    cyc = cycle[:-1]
                    min_idx = cyc.index(min(cyc))
                    normalized = cyc[min_idx:] + cyc[:min_idx]
                    if normalized not in cycles:
                        cycles.append(normalized)

            path.pop()
            rec_stack.remove(node)

        for start in sorted(scc):
            visited.clear()
            rec_stack.clear()
            path.clear()
            dfs(start)

    return cycles


def find_large_files(files, threshold=1000):
    large = []
    for f in files:
        if f.suffix == '.py':
            rel = str(f.relative_to(PROJECT_ROOT)).replace(os.sep, '/')
            if 'docs/architecture/' in rel:
                continue
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    lines = sum(1 for _ in fh)
                if lines > threshold:
                    large.append((lines, rel))
            except Exception:
                pass
    return sorted(large, reverse=True)


def find_all_files_by_lines(files):
    all_files = []
    for f in files:
        if f.suffix == '.py':
            rel = str(f.relative_to(PROJECT_ROOT)).replace(os.sep, '/')
            if 'docs/architecture/' in rel:
                continue
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    lines = sum(1 for _ in fh)
                all_files.append((lines, rel))
            except Exception:
                pass
    return sorted(all_files, reverse=True)


def find_duplicate_configs(files):
    json_files = [f for f in files if f.suffix == '.json' and 'data' not in str(f).replace(os.sep, '/') and 'docs/architecture/' not in str(f).replace(os.sep, '/')]

    configs = {}
    for f in json_files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            configs[str(f).replace(os.sep, '/')] = data
        except Exception:
            pass

    key_locations = defaultdict(list)
    for path, data in configs.items():
        if isinstance(data, dict):
            for key in data.keys():
                key_locations[key].append(path)

    duplicate_keys = {k: v for k, v in key_locations.items() if len(v) > 1}

    value_locations = defaultdict(list)
    for path, data in configs.items():
        if isinstance(data, dict):
            for key, val in data.items():
                try:
                    val_str = json.dumps(val, sort_keys=True)
                    value_locations[val_str].append((path, key))
                except Exception:
                    pass

    duplicate_values = {k: v for k, v in value_locations.items() if len(v) > 1}

    return {
        "duplicate_keys": duplicate_keys,
        "duplicate_values": duplicate_values,
        "configs_found": list(configs.keys())
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/6] Scanning project files...")
    files = get_all_files()
    print(f"    Found {len(files)} files")

    print("[2/6] Generating directory tree...")
    tree = generate_directory_tree()
    with open(OUTPUT_DIR / "directory_tree.txt", "w", encoding="utf-8") as f:
        f.write(tree)
    print("    Written directory_tree.txt")

    print("[3/6] Analyzing module dependencies...")
    deps = analyze_dependencies(files)
    with open(OUTPUT_DIR / "module_dependencies.json", "w", encoding="utf-8") as f:
        json.dump(deps["module_imports"], f, indent=2)
    with open(OUTPUT_DIR / "subpackage_dependencies.json", "w", encoding="utf-8") as f:
        json.dump(deps["subpackage_dependencies"], f, indent=2)
    with open(OUTPUT_DIR / "detailed_imports.json", "w", encoding="utf-8") as f:
        json.dump(deps["detailed_imports"], f, indent=2)
    print("    Written dependency JSONs")

    print("[4/6] Finding circular dependencies...")
    cycles = find_cycles(deps["module_imports"])
    with open(OUTPUT_DIR / "circular_dependencies.txt", "w", encoding="utf-8") as f:
        if cycles:
            f.write("Found circular dependencies:\n\n")
            for i, cycle in enumerate(cycles, 1):
                f.write(f"Cycle {i}: {' -> '.join(cycle)} -> {cycle[0]}\n")
        else:
            f.write("No circular dependencies found at module level.\n")
    print(f"    Found {len(cycles)} cycles")

    print("[5/6] Finding large files and duplicates...")
    large_files = find_large_files(files, threshold=1000)
    with open(OUTPUT_DIR / "large_files.txt", "w", encoding="utf-8") as f:
        if large_files:
            f.write(f"Files over 1000 lines ({len(large_files)} found):\n\n")
            for lines, path in large_files:
                f.write(f"  {lines:>5} lines  {path}\n")
        else:
            f.write("No Python files exceed 1000 lines.\n\n")
            f.write("Top 15 largest files:\n")
            all_files = find_all_files_by_lines(files)
            for lines, path in all_files[:15]:
                f.write(f"  {lines:>5} lines  {path}\n")
    print("    Written large_files.txt")

    dup_configs = find_duplicate_configs(files)
    with open(OUTPUT_DIR / "duplicate_configs.txt", "w", encoding="utf-8") as f:
        f.write("Configuration files analyzed:\n")
        for cf in dup_configs["configs_found"]:
            f.write(f"  - {cf}\n")
        f.write("\n")

        if dup_configs["duplicate_keys"]:
            f.write("Duplicate keys found across files:\n")
            for key, locations in dup_configs["duplicate_keys"].items():
                f.write(f"  '{key}' in: {', '.join(locations)}\n")
        else:
            f.write("No duplicate keys found across configuration files.\n")

        f.write("\n")
        if dup_configs["duplicate_values"]:
            f.write("Duplicate values found across files:\n")
            for val_str, locations in dup_configs["duplicate_values"].items():
                if len(val_str) > 100:
                    val_str = val_str[:100] + "..."
                paths = [f"{p}[{k}]" for p, k in locations]
                f.write(f"  Value: {val_str}\n")
                f.write(f"    Locations: {', '.join(paths)}\n")
        else:
            f.write("No duplicate values found across configuration files.\n")
    print("    Written duplicate_configs.txt")

    print("[6/6] Generating architecture_report.md...")
    report = generate_report(files, tree, deps, cycles, large_files, dup_configs)
    with open(OUTPUT_DIR / "architecture_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("    Written architecture_report.md")

    print("Done!")


def generate_report(files, tree, deps, cycles, large_files, dup_configs):
    py_files = [f for f in files if f.suffix == '.py']
    total_py_lines = 0
    for f in py_files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                total_py_lines += sum(1 for _ in fh)
        except Exception:
            pass

    # Build import table
    import_table = ""
    for mod, imports in sorted(deps["module_imports"].items()):
        imports_str = ', '.join([f"`{i}`" for i in imports[:5]])
        if len(imports) > 5:
            imports_str += f" ... (+{len(imports) - 5} more)"
        import_table += f"| `{mod}` | {imports_str or '-'} |\n"

    # Subpackage deps
    subpkg_table = ""
    for pkg, dep_pkgs in sorted(deps["subpackage_dependencies"].items()):
        subpkg_table += f"| `{pkg}` | {', '.join([f'`{d}`' for d in dep_pkgs]) or '-'} |\n"

    cycles_section = ""
    if cycles:
        cycles_section = "**⚠️ Found circular dependencies:**\n\n"
        for i, cycle in enumerate(cycles, 1):
            cycles_section += f"{i}. `{' -> '.join(cycle)} -> {cycle[0]}`\n"
    else:
        cycles_section = "✅ **No circular dependencies detected at module level.**\n"

    large_section = ""
    if large_files:
        large_section = f"**Found {len(large_files)} files exceeding 1000 lines:**\n\n"
        for lines, path in large_files:
            large_section += f"- `{path}` — {lines} lines\n"
    else:
        large_section = "No Python files exceed 1000 lines.\n\n"
        large_section += "### Top 15 Largest Files\n\n"
        large_section += "| Lines | File |\n|-------|------|\n"
        all_files = find_all_files_by_lines(files)
        for lines, path in all_files[:15]:
            large_section += f"| {lines} | `{path}` |\n"

    dup_keys_section = ""
    if dup_configs["duplicate_keys"]:
        dup_keys_section = "| Key | Found In |\n|-----|----------|\n"
        for key, locations in dup_configs["duplicate_keys"].items():
            dup_keys_section += f"| `{key}` | {', '.join(locations)} |\n"
    else:
        dup_keys_section = "No duplicate keys detected across configuration files.\n"

    dup_vals_section = ""
    if dup_configs["duplicate_values"]:
        dup_vals_section = "| Value Preview | Locations |\n|---------------|-----------|\n"
        for val_str, locations in list(dup_configs["duplicate_values"].items())[:10]:
            preview = val_str[:80] + "..." if len(val_str) > 80 else val_str
            paths = [f"`{p}[{k}]`" for p, k in locations]
            dup_vals_section += f"| `{preview}` | {', '.join(paths)} |\n"
    else:
        dup_vals_section = "No duplicate values detected across configuration files.\n"

    report = f"""# VCW Project Architecture Report

> Generated: 2026-05-30
> Analyzer: Python Architecture Scanner

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total Python Files | {len(py_files)} |
| Total Python LOC | {total_py_lines} |
| Config Files (JSON/INI) | {len(dup_configs['configs_found'])} |
| Circular Dependencies | {len(cycles)} |
| Files > 1000 Lines | {len(large_files)} |

---

## 2. Directory Tree

```
{tree}
```

---

## 3. Module Dependency Analysis

### 3.1 Top-Level Package Dependencies

| Package | Imports From |
|---------|-------------|
{subpkg_table}

### 3.2 Detailed Module Import Map

| Module | Imports |
|--------|---------|
{import_table}

---

## 4. Circular Dependencies

{cycles_section}

---

## 5. Large File Analysis

{large_section}

---

## 6. Configuration Duplication Analysis

### Analyzed Config Files

"""
    for cf in dup_configs["configs_found"]:
        report += f"- `{cf}`\n"

    report += f"""
### Duplicate Keys

{dup_keys_section}

### Duplicate Values

{dup_vals_section}

---

## 7. Recommendations

1. **Modularization**: If files grow beyond 1000 lines, consider splitting responsibilities.
2. **Dependency Direction**: Ensure `app/` depends on `vcw_copywriter/`, not vice versa.
3. **Configuration Centralization**: Avoid scattering config keys; use a single source of truth.
4. **Test Coverage**: Ensure all API routes and services have corresponding tests.

---

*End of Report*
"""
    return report


if __name__ == "__main__":
    main()
