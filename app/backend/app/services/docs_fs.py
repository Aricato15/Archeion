"""Reading docs/: the tree, files, the roadmap, diagrams, search and section excerpts."""

from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..paths import ALLOWED_EXT, MARKDOWN_EXT, MAX_FILE_BYTES

FENCE_RE = re.compile(r"^\s{0,3}(```+|~~~+)\s*([\w-]*)")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _visible(p: Path) -> bool:
    return not p.name.startswith(".")


def iter_files(docs_root: Path, exts: set[str] | None = None) -> list[Path]:
    """All visible files under docs_root with an allowed extension, sorted, no symlinks out."""
    exts = exts or ALLOWED_EXT
    root = docs_root.resolve()
    out = []
    for p in sorted(root.rglob("*")):
        rel_parts = p.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        if not p.resolve().is_relative_to(root):
            continue
        out.append(p)
    return out


def tree(docs_root: Path) -> dict:
    """Nested tree of docs/: directories first, then files, each sorted by name."""
    root = docs_root.resolve()

    def walk(d: Path) -> list[dict]:
        entries = sorted((p for p in d.iterdir() if _visible(p)), key=lambda p: (p.is_file(), p.name.lower()))
        children = []
        for p in entries:
            rel = p.relative_to(root).as_posix()
            if p.is_dir() and not p.is_symlink():
                children.append({"name": p.name, "path": rel, "type": "dir", "children": walk(p)})
            elif p.is_file() and p.suffix.lower() in ALLOWED_EXT and p.resolve().is_relative_to(root):
                children.append({"name": p.name, "path": rel, "type": "file"})
        return children

    return {"name": "docs", "path": "", "type": "dir", "children": walk(root) if root.is_dir() else []}


def read_text(path: Path) -> str:
    data = path.read_bytes()[:MAX_FILE_BYTES]
    return data.decode("utf-8", errors="replace")


def file_info(path: Path, rel: str) -> dict:
    content = read_text(path)
    stat = path.stat()
    return {
        "path": rel,
        "content": content,
        "sha": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds"),
    }


# --- markdown structure -----------------------------------------------------------------


@dataclass
class Block:
    """A fenced code block found while scanning a Markdown file."""

    lang: str
    start_line: int  # 1-based line of the opening fence
    lines: list[str] = field(default_factory=list)


def scan(content: str) -> tuple[list[tuple[int, int, str]], list[tuple[Block, str | None]]]:
    """Headings (line, level, text) outside code fences, and fenced blocks with their heading."""
    headings: list[tuple[int, int, str]] = []
    blocks: list[tuple[Block, str | None]] = []
    current: Block | None = None
    fence = ""
    last_heading: str | None = None
    for i, line in enumerate(content.splitlines(), start=1):
        if current is not None:
            if line.strip().startswith(fence[0] * len(fence)) and line.strip().strip(fence[0]) == "":
                blocks.append((current, last_heading))
                current = None
            else:
                current.lines.append(line)
            continue
        m = FENCE_RE.match(line)
        if m:
            fence = m.group(1)
            current = Block(lang=m.group(2).lower(), start_line=i)
            continue
        h = HEADING_RE.match(line)
        if h:
            text = h.group(2).strip()
            headings.append((i, len(h.group(1)), text))
            last_heading = text
    return headings, blocks


def diagrams(docs_root: Path) -> list[dict]:
    out = []
    root = docs_root.resolve()
    for p in iter_files(root, {MARKDOWN_EXT}):
        rel = p.relative_to(root).as_posix()
        _, blocks = scan(read_text(p))
        index = 0
        for block, heading in blocks:
            if block.lang != "mermaid":
                continue
            out.append(
                {
                    "path": rel,
                    "heading": heading,
                    "index": index,
                    "line": block.start_line,
                    "source": "\n".join(block.lines),
                }
            )
            index += 1
    return out


def search(docs_root: Path, q: str, limit: int = 200) -> list[dict]:
    needle = q.casefold()
    out: list[dict] = []
    root = docs_root.resolve()
    for p in iter_files(root, {MARKDOWN_EXT}):
        rel = p.relative_to(root).as_posix()
        for i, line in enumerate(read_text(p).splitlines(), start=1):
            if needle in line.casefold():
                out.append({"path": rel, "line": i, "snippet": line.strip()[:200]})
                if len(out) >= limit:
                    return out
    return out


def excerpt(
    content: str,
    *,
    lines: tuple[int, int] | None = None,
    heading: str | None = None,
    context: int = 3,
    max_lines: int = 60,
) -> str:
    """The part of a doc an anchor points at, for the inbox CLI."""
    all_lines = content.splitlines()
    if lines:
        start = max(1, lines[0] - context)
        end = min(len(all_lines), lines[1] + context)
    elif heading:
        headings, _ = scan(content)
        match = next(((ln, lvl) for ln, lvl, text in headings if text == heading), None)
        if match is None:
            return ""
        start, level = match
        end = len(all_lines)
        for ln, lvl, _ in headings:
            if ln > start and lvl <= level:
                end = ln - 1
                break
    else:
        return ""
    end = min(end, start + max_lines - 1)
    width = len(str(end))
    return "\n".join(f"{n:>{width}} | {all_lines[n - 1]}" for n in range(start, end + 1))


# --- roadmap ----------------------------------------------------------------------------


def _resolve_link(from_rel: str, href: str) -> str | None:
    """Docs-relative path a relative link points at, or None if it leaves docs/ or is external."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith(("#", "/")):
        return None
    target = href.split("#", 1)[0]
    if not target:
        return None
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), target))
    if joined.startswith("../") or joined == "..":
        return None
    return joined


def roadmap(docs_root: Path) -> dict:
    rel = "roadmap/roadmap.md"
    path = docs_root / rel
    result: dict = {"path": rel, "updated": None, "now": [], "next": [], "later": [], "plans": []}
    if path.is_file():
        section: str | None = None
        for line in read_text(path).splitlines():
            m = re.match(r"^_Last updated:\s*(.+?)_\s*$", line.strip())
            if m:
                result["updated"] = m.group(1)
                continue
            h = re.match(r"^##\s+(Now|Next|Later)\s*$", line.strip(), re.I)
            if h:
                section = h.group(1).lower()
                continue
            if line.startswith("## "):
                section = None
                continue
            if section and re.match(r"^[-*]\s+", line):
                text = re.sub(r"^[-*]\s+", "", line).strip()
                links = []
                for label, href in LINK_RE.findall(text):
                    target = _resolve_link(rel, href)
                    if target:
                        links.append({"label": label, "path": target})
                result[section].append({"text": text, "links": links})
    plans_dir = docs_root / "roadmap"
    if plans_dir.is_dir():
        for p in sorted(plans_dir.glob("*.md"), reverse=True):
            if p.name == "roadmap.md" or p.name.startswith("."):
                continue
            title = p.stem
            headings, _ = scan(read_text(p))
            if headings:
                title = headings[0][2]
            date = re.match(r"^(\d{4}-\d{2}-\d{2})", p.name)
            result["plans"].append(
                {"path": f"roadmap/{p.name}", "title": title, "date": date.group(1) if date else None}
            )
    return result
