"""`study scan`: a deterministic, read-only inventory of a project's code (ADR 0019).

It grounds a study in facts found by parsing rather than recalled: languages and sizes,
manifests and their dependencies, entry points, an import graph, route declarations, outgoing
HTTP calls, SQL tables, environment variable names and ports. Python is parsed with `ast`;
TypeScript and JavaScript with patterns. Nothing is executed, and environments, build
output, dotfiles, .env files, keys and databases are never opened.

Every path in the output is relative to the project folder.
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SKIP_DIRS = {
    "node_modules", "venv", ".venv", "__pycache__", "dist", "build", "target",
    "coverage", "htmlcov", "site-packages", "vendor", "bower_components", "backups",
}  # fmt: skip
SKIP_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".pem", ".key", ".pfx", ".p12", ".crt",
    ".lock", ".map", ".min.js", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".exe", ".dll", ".so", ".pyc", ".woff", ".woff2", ".ttf",
}  # fmt: skip
LANGS = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".sql": "sql",
    ".ps1": "powershell", ".bat": "batch", ".sh": "shell", ".go": "go", ".rs": "rust",
    ".java": "java", ".kt": "kotlin", ".cs": "csharp", ".rb": "ruby", ".php": "php",
    ".html": "html", ".css": "css", ".scss": "css", ".md": "markdown", ".toml": "toml",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json",
}  # fmt: skip
CODE_LANGS = {"python", "typescript", "javascript"}
CONFIG_NAMES = {".env.example", "config.py", "settings.py", "vite.config.ts", "vite.config.js",
                "docker-compose.yml", "docker-compose.yaml", "settings.schema.json"}  # fmt: skip
MAX_FILES = 8000
MAX_FILE_BYTES = 1024 * 1024
PORT_RANGE = (20000, 20799)

HTTP_LIBS = {"requests", "httpx", "aiohttp", "urllib3"}
HTTP_CLIENTS = {"Client", "AsyncClient", "Session", "ClientSession", "PoolManager"}
# Calls on a variable or attribute named like this are likely HTTP calls through a client.
_CLIENTISH = re.compile(r"(?i)(^|_)(client|session|http)s?$")
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "request", "stream"}
ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "route", "websocket",
                 "api_route"}  # fmt: skip

_TS_IMPORT = re.compile(
    r"""(?:^|[;\s])(?:import\s+(?:type\s+)?(?:[\w*{}\s,]+\s+from\s+)?|export\s+[\w*{}\s,]+\s+from\s+)"""
    r"""['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|import\(\s*['"]([^'"]+)['"]\s*\)""",
    re.M,
)
_TS_DEF = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(function|class|const|let|interface|type|enum)\s+(\w+)", re.M
)
_TS_ROUTE = re.compile(
    r"""\b(app|router|server|api)\.(get|post|put|patch|delete|all|use)\(\s*['"`](/[^'"`]*)['"`]"""
)
_TS_FETCH = re.compile(r"""\bfetch\(\s*(['"`])([^'"`]*)\1""")
_TS_AXIOS = re.compile(r"""\b(axios|http|client|api)\.(get|post|put|patch|delete)\(\s*(['"`])([^'"`]*)\3""")
_TS_ENV = re.compile(r"\b(?:process\.env|import\.meta\.env)\.([A-Z][A-Z0-9_]*)")
_SQL_TABLE = re.compile(r"(?i)\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?[\"'`\[]?([A-Za-z_][\w]*)")
_PORT = re.compile(r"(?<![\d.])(20[0-7]\d\d)(?![\d.])")


@dataclass
class Inventory:
    project: str
    commit: str | None = None
    dirty: bool | None = None
    files_total: int = 0
    truncated: bool = False
    languages: dict[str, dict[str, int]] = field(default_factory=dict)
    manifests: list[dict] = field(default_factory=list)
    entry_points: list[dict] = field(default_factory=list)
    modules: list[dict] = field(default_factory=list)
    package_graph: list[dict] = field(default_factory=list)
    external_imports: dict[str, int] = field(default_factory=dict)
    routes: list[dict] = field(default_factory=list)
    http_calls: list[dict] = field(default_factory=list)
    # Where HTTP clients are built (with their base_url), since calls made through a shared
    # client elsewhere can't be followed statically.
    http_clients: list[dict] = field(default_factory=list)
    sql_tables: list[dict] = field(default_factory=list)
    env_vars: list[dict] = field(default_factory=list)
    ports: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    # Folders left out of the scan, relative to the root: a group's members, which have studies of their own.
    excluded: list[str] = field(default_factory=list)

    def public(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _skip_file(name: str) -> bool:
    low = name.lower()
    if low == ".env" or (low.startswith(".env.") and low != ".env.example"):
        return True
    if name.startswith(".") and low != ".env.example":
        return True
    return any(low.endswith(s) for s in SKIP_SUFFIXES)


def walk(root: Path, exclude: frozenset[Path] | None = None) -> tuple[list[str], bool]:
    """Every file worth reading, relative and sorted; and whether the walk stopped at MAX_FILES.
    Folders in `exclude` (resolved paths) are left out with everything under them."""
    out: list[str] = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = sorted(d.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for p in entries:
            if p.is_symlink():
                continue
            if p.is_dir():
                if p.name.startswith(".") or p.name in SKIP_DIRS or (p / "pyvenv.cfg").exists():
                    continue
                if exclude and p.resolve() in exclude:
                    continue
                stack.append(p)
            elif p.is_file() and not _skip_file(p.name):
                out.append(p.relative_to(root).as_posix())
                if len(out) >= MAX_FILES:
                    return sorted(out), True
    return sorted(out), False


def _lang(rel: str) -> str | None:
    name = rel.rsplit("/", 1)[-1].lower()
    for ext in sorted(LANGS, key=len, reverse=True):
        if name.endswith(ext):
            return LANGS[ext]
    return None


def _read(root: Path, rel: str) -> str | None:
    p = root / rel
    try:
        if p.stat().st_size > MAX_FILE_BYTES:
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


# --- manifests --------------------------------------------------------------------------


def _manifests(root: Path, files: list[str], inv: Inventory) -> None:
    for rel in files:
        name = rel.rsplit("/", 1)[-1]
        if name == "pyproject.toml":
            text = _read(root, rel)
            try:
                data = tomllib.loads(text or "")
            except tomllib.TOMLDecodeError:
                inv.manifests.append({"path": rel, "kind": "pyproject", "error": "invalid TOML"})
                continue
            proj = data.get("project", {})
            groups = data.get("dependency-groups", {})
            scripts = proj.get("scripts", {})
            inv.manifests.append(
                {
                    "path": rel,
                    "kind": "pyproject",
                    "name": proj.get("name"),
                    "python": proj.get("requires-python"),
                    "dependencies": proj.get("dependencies", []),
                    "dev_dependencies": [d for g in groups.values() for d in g if isinstance(d, str)],
                    "scripts": scripts,
                }
            )
            for script, target in scripts.items():
                inv.entry_points.append({"kind": "script", "name": script, "target": target, "path": rel})
        elif name == "package.json":
            try:
                data = json.loads(_read(root, rel) or "{}")
            except json.JSONDecodeError:
                inv.manifests.append({"path": rel, "kind": "npm", "error": "invalid JSON"})
                continue
            inv.manifests.append(
                {
                    "path": rel,
                    "kind": "npm",
                    "name": data.get("name"),
                    "dependencies": sorted(data.get("dependencies", {})),
                    "dev_dependencies": sorted(data.get("devDependencies", {})),
                    "scripts": data.get("scripts", {}),
                }
            )
            if data.get("main"):
                inv.entry_points.append({"kind": "main", "target": data["main"], "path": rel})
        elif re.fullmatch(r"requirements[\w.-]*\.txt", name):
            lines = [
                ln.strip()
                for ln in (_read(root, rel) or "").splitlines()
                if ln.strip() and not ln.startswith(("#", "-"))
            ]
            inv.manifests.append({"path": rel, "kind": "requirements", "dependencies": lines})


# --- python -----------------------------------------------------------------------------


def _py_module_name(rel: str, roots: list[str]) -> str:
    """Dotted module name, relative to the deepest source root (a folder above a package)."""
    p = PurePosixPath(rel)
    for r in sorted(roots, key=len, reverse=True):
        if r == "" or rel.startswith(r + "/"):
            p = PurePosixPath(rel[len(r) + 1 :] if r else rel)
            break
    parts = list(p.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _py_roots(files: list[str]) -> list[str]:
    """Folders that hold top-level packages: the parent of every package whose parent isn't one."""
    inits = {str(PurePosixPath(f).parent) for f in files if f.endswith("/__init__.py") or f == "__init__.py"}
    roots = set()
    for pkg in inits:
        parent = str(PurePosixPath(pkg).parent)
        if parent not in inits:
            roots.add("" if parent == "." else parent)
    # Loose scripts and flat layouts: every folder holding .py files counts too.
    for f in files:
        if f.endswith(".py"):
            parent = str(PurePosixPath(f).parent)
            if parent not in inits:
                roots.add("" if parent == "." else parent)
    return sorted(roots)


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    return ""


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            parts.append(v.value if isinstance(v, ast.Constant) else "{…}")
        return "".join(str(p) for p in parts)
    return None


def _scan_python(root: Path, rel: str, text: str, modname: str, inv: Inventory) -> dict:
    mod = {"path": rel, "lang": "python", "module": modname, "lines": text.count("\n") + 1}
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        mod["error"] = f"syntax error at line {exc.lineno}"
        return mod
    imports: list[tuple[str, int]] = []
    defs: list[dict] = []
    http_aliases = set(HTTP_LIBS)
    pkg = modname.rsplit(".", 1)[0] if not rel.endswith("__init__.py") else modname
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append((a.name, node.lineno))
                if a.name.split(".")[0] in HTTP_LIBS and a.asname:
                    http_aliases.add(a.asname)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = pkg.split(".") if pkg else []
                up = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join([*up, *([node.module] if node.module else [])])
            if node.module is None and node.level:
                for a in node.names:
                    imports.append((f"{base}.{a.name}" if base else a.name, node.lineno))
            else:
                imports.append((base, node.lineno))
        elif isinstance(node, ast.Call):
            func = _dotted(node.func)
            parts = func.split(".")
            if len(parts) == 2 and parts[0] in http_aliases and parts[1] in HTTP_CLIENTS:
                base = next((_const_str(k.value) for k in node.keywords if k.arg == "base_url"), None)
                inv.http_clients.append(
                    {"path": rel, "line": node.lineno, "lib": parts[0], "client": parts[1], "base_url": base}
                )
            elif len(parts) >= 2 and parts[-1] in HTTP_METHODS and _CLIENTISH.search(parts[-2]):
                url = _const_str(node.args[0]) if node.args else None
                inv.http_calls.append(
                    {
                        "path": rel,
                        "line": node.lineno,
                        "lib": "client?",
                        "method": parts[-1].upper(),
                        "url": url,
                    }
                )
            elif len(parts) >= 2 and parts[0] in http_aliases and parts[-1] in HTTP_METHODS:
                url = _const_str(node.args[0]) if node.args else None
                if parts[-1] == "request" and len(node.args) > 1:
                    url = _const_str(node.args[1])
                inv.http_calls.append(
                    {
                        "path": rel,
                        "line": node.lineno,
                        "lib": parts[0],
                        "method": parts[-1].upper(),
                        "url": url,
                    }
                )
            elif func in ("os.getenv", "os.environ.get", "environ.get", "getenv") and node.args:
                name = _const_str(node.args[0])
                if name:
                    inv.env_vars.append({"name": name, "path": rel, "line": node.lineno})
            elif func in ("uvicorn.run", "app.run") or func.endswith((".run_forever", "serve_forever")):
                inv.entry_points.append({"kind": "server", "target": func, "path": rel, "line": node.lineno})
            elif func == "sqlite3.connect":
                inv.entry_points.append(
                    {"kind": "sqlite", "target": "sqlite3.connect", "path": rel, "line": node.lineno}
                )
        elif isinstance(node, ast.Subscript) and _dotted(node.value) in ("os.environ", "environ"):
            name = _const_str(node.slice)
            if name:
                inv.env_vars.append({"name": name, "path": rel, "line": node.lineno})
        elif isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and any(_const_str(c) == "__main__" for c in test.comparators)
            ):
                inv.entry_points.append({"kind": "main", "target": modname, "path": rel, "line": node.lineno})
    # Top-level definitions and methods, with routes from their decorators.
    prefixes: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            callee = _dotted(node.value.func).rsplit(".", 1)[-1]
            if callee in ("APIRouter", "Blueprint", "FastAPI", "Flask"):
                prefix = next(
                    (_const_str(k.value) for k in node.value.keywords if k.arg in ("prefix", "url_prefix")),
                    "",
                )
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        prefixes[t.id] = prefix or ""
                        if callee in ("FastAPI", "Flask"):
                            inv.entry_points.append(
                                {"kind": "app", "target": f"{callee}()", "path": rel, "line": node.lineno}
                            )

    def visit_defs(body: list[ast.stmt], owner: str | None) -> None:
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                kind = "class" if isinstance(node, ast.ClassDef) else ("method" if owner else "function")
                name = f"{owner}.{node.name}" if owner else node.name
                defs.append({"name": name, "kind": kind, "line": node.lineno, "end": node.end_lineno})
                for dec in getattr(node, "decorator_list", []):
                    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                        continue
                    method = dec.func.attr
                    obj = _dotted(dec.func.value)
                    if method not in ROUTE_METHODS:
                        continue
                    route = _const_str(dec.args[0]) if dec.args else None
                    if route is None:
                        continue
                    methods = method.upper()
                    for k in dec.keywords:
                        if k.arg == "methods" and isinstance(k.value, ast.List | ast.Tuple):
                            methods = ",".join(str(_const_str(e)) for e in k.value.elts)
                    inv.routes.append(
                        {
                            "path": rel,
                            "line": node.lineno,
                            "method": methods,
                            "route": prefixes.get(obj, "") + route,
                            "handler": f"{modname}.{name}",
                            "framework": "python",
                        }
                    )
                if isinstance(node, ast.ClassDef):
                    visit_defs(node.body, node.name)

    visit_defs(tree.body, None)
    mod["imports"] = sorted({i for i, _ in imports if i})
    mod["defs"] = defs
    return mod


# --- typescript / javascript ------------------------------------------------------------

_TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _resolve_ts(rel: str, spec: str, files: set[str]) -> str | None:
    base = PurePosixPath(rel).parent / spec
    parts: list[str] = []
    for part in base.parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part != ".":
            parts.append(part)
    cand = "/".join(parts)
    options = [cand, *(cand + e for e in _TS_EXTS), *(f"{cand}/index{e}" for e in _TS_EXTS)]
    # "./x.js" written for a .ts file (ESM style).
    stem = re.sub(r"\.(js|jsx|mjs)$", "", cand)
    options += [stem + e for e in _TS_EXTS]
    return next((o for o in options if o in files), None)


def _scan_ts(rel: str, text: str, files: set[str], inv: Inventory, lang: str) -> dict:
    mod: dict = {"path": rel, "lang": lang, "lines": text.count("\n") + 1}
    internal: set[str] = set()
    external: set[str] = set()
    for m in _TS_IMPORT.finditer(text):
        spec = m.group(1) or m.group(2) or m.group(3)
        if not spec:
            continue
        if spec.startswith("."):
            target = _resolve_ts(rel, spec, files)
            internal.add(target or spec)
        else:
            pkg = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            external.add(pkg)
    mod["imports"] = sorted(internal)
    mod["external"] = sorted(external)
    mod["defs"] = [
        {"name": m.group(2), "kind": m.group(1), "line": _line_of(text, m.start())}
        for m in _TS_DEF.finditer(text)
    ]
    for m in _TS_ROUTE.finditer(text):
        inv.routes.append(
            {
                "path": rel,
                "line": _line_of(text, m.start()),
                "method": m.group(2).upper(),
                "route": m.group(3),
                "framework": "js",
            }
        )
    for m in _TS_FETCH.finditer(text):
        inv.http_calls.append(
            {
                "path": rel,
                "line": _line_of(text, m.start()),
                "lib": "fetch",
                "method": None,
                "url": m.group(2),
            }
        )
    for m in _TS_AXIOS.finditer(text):
        inv.http_calls.append(
            {
                "path": rel,
                "line": _line_of(text, m.start()),
                "lib": m.group(1),
                "method": m.group(2).upper(),
                "url": m.group(4),
            }
        )
    for m in _TS_ENV.finditer(text):
        inv.env_vars.append({"name": m.group(1), "path": rel, "line": _line_of(text, m.start())})
    return mod


# --- the scan ---------------------------------------------------------------------------


def _package_of(rel: str) -> str:
    parent = str(PurePosixPath(rel).parent)
    return "." if parent == "." else parent


def scan(
    root: Path,
    project: str,
    commit: str | None = None,
    dirty: bool | None = None,
    exclude: list[Path] | None = None,
) -> Inventory:
    inv = Inventory(project=project, commit=commit, dirty=dirty)
    skip = frozenset(p.resolve() for p in exclude or [])
    inv.excluded = sorted(
        p.relative_to(root.resolve()).as_posix() for p in skip if p.is_relative_to(root.resolve())
    )
    files, inv.truncated = walk(root, skip)
    inv.files_total = len(files)
    fileset = set(files)
    langs: dict[str, Counter] = defaultdict(Counter)
    _manifests(root, files, inv)
    py_files = [f for f in files if f.endswith(".py")]
    roots = _py_roots(py_files)
    py_modules: dict[str, str] = {}  # dotted name -> rel path
    for f in py_files:
        py_modules[_py_module_name(f, roots)] = f
    top_packages = {name.split(".")[0] for name in py_modules if name}

    for rel in files:
        lang = _lang(rel)
        text = _read(root, rel)
        if text is None:
            inv.skipped.append(rel)
            continue
        if lang:
            langs[lang]["files"] += 1
            langs[lang]["lines"] += text.count("\n") + 1
        name = rel.rsplit("/", 1)[-1]
        if lang == "python":
            mod = _scan_python(root, rel, text, _py_module_name(rel, roots), inv)
            internal, external = set(), set()
            for imp in mod.get("imports", []):
                if imp.split(".")[0] in top_packages:
                    # The longest dotted prefix that's a module of this project.
                    parts = imp.split(".")
                    for n in range(len(parts), 0, -1):
                        target = py_modules.get(".".join(parts[:n]))
                        if target:
                            if target != rel:
                                internal.add(target)
                            break
                else:
                    external.add(imp.split(".")[0])
            mod["imports"] = sorted(internal)
            mod["external"] = sorted(external)
            inv.modules.append(mod)
        elif lang in ("typescript", "javascript") and not name.endswith(".d.ts"):
            inv.modules.append(_scan_ts(rel, text, fileset, inv, lang))
        if lang in ("sql", "python", "typescript", "javascript"):
            for m in _SQL_TABLE.finditer(text):
                inv.sql_tables.append({"name": m.group(1), "path": rel, "line": _line_of(text, m.start())})
        if (
            name in CONFIG_NAMES
            or name.endswith((".env.example", ".toml", ".yaml", ".yml"))
            or name == "CLAUDE.md"
        ):
            for m in _PORT.finditer(text):
                port = int(m.group(1))
                if PORT_RANGE[0] <= port <= PORT_RANGE[1]:
                    inv.ports.append({"port": port, "path": rel, "line": _line_of(text, m.start())})

    inv.languages = {k: dict(v) for k, v in sorted(langs.items(), key=lambda kv: -kv[1]["lines"])}
    edges: Counter = Counter()
    ext_count: Counter = Counter()
    stdlib = _stdlib()
    for mod in inv.modules:
        src = _package_of(mod["path"])
        for target in mod.get("imports", []):
            if target in fileset:
                dst = _package_of(target)
                if dst != src:
                    edges[(src, dst)] += 1
        for pkg in mod.get("external", []):
            if mod["lang"] == "python" and pkg in stdlib:
                continue
            ext_count[pkg] += 1
    inv.package_graph = [{"from": a, "to": b, "imports": n} for (a, b), n in sorted(edges.items())]
    inv.external_imports = dict(ext_count.most_common())
    return inv


def _stdlib() -> frozenset[str]:
    import sys

    return frozenset(getattr(sys, "stdlib_module_names", ())) | {"__future__"}


def text_report(inv: Inventory) -> str:
    """The short version for the terminal; --json has everything."""
    out = [
        f"{inv.project}: {inv.files_total} files" + (" (stopped at the file limit)" if inv.truncated else "")
    ]
    if inv.commit:
        out.append(f"  commit {inv.commit[:10]}" + (" (uncommitted changes)" if inv.dirty else ""))
    out.append(
        "  languages: "
        + ", ".join(f"{k} {v['files']} files/{v['lines']} lines" for k, v in inv.languages.items())
    )
    for m in inv.manifests:
        deps = m.get("dependencies", [])
        out.append(f"  manifest {m['path']} ({m['kind']}): {len(deps)} dependencies")
    if inv.entry_points:
        out.append("  entry points:")
        out += [
            f"    {e['kind']}: {e.get('target')} ({e['path']}{':' + str(e['line']) if e.get('line') else ''})"
            for e in inv.entry_points[:30]
        ]
    code = [m for m in inv.modules if m["lang"] in CODE_LANGS]
    out.append(f"  modules: {len(code)}; package edges: {len(inv.package_graph)}")
    for e in inv.package_graph[:40]:
        out.append(f"    {e['from']} -> {e['to']} ({e['imports']})")
    if inv.external_imports:
        out.append(
            "  external imports: "
            + ", ".join(f"{k} ({v})" for k, v in list(inv.external_imports.items())[:30])
        )
    out.append(f"  routes: {len(inv.routes)}")
    out += [f"    {r['method']} {r['route']}  {r['path']}:{r['line']}" for r in inv.routes[:60]]
    if inv.http_clients:
        out.append(f"  http clients built: {len(inv.http_clients)}")
        out += [
            f"    {c['lib']}.{c['client']} base_url={c.get('base_url') or '(dynamic)'}"
            f"  {c['path']}:{c['line']}"
            for c in inv.http_clients[:20]
        ]
    out.append(
        f"  outgoing http calls: {len(inv.http_calls)} ('client?' = through a client variable, likely)"
    )
    out += [
        f"    {c.get('method') or '?'} {c.get('url') or '(dynamic)'}  {c['path']}:{c['line']}"
        for c in inv.http_calls[:40]
    ]
    out.append("  sql tables: " + (", ".join(sorted({t["name"] for t in inv.sql_tables})) or "none"))
    out.append("  env vars: " + (", ".join(sorted({e["name"] for e in inv.env_vars})) or "none"))
    out.append("  ports: " + (", ".join(str(p) for p in sorted({p["port"] for p in inv.ports})) or "none"))
    return "\n".join(out)
