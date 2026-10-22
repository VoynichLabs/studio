"""
Author: Claude Opus 5.5 Medium
Date: 22-October-2026
PURPOSE: Small, careful edits to a song file without rewriting it, so comments and layout that
Claude or the Boss wrote stay exactly as they were. Sets one value inside one table (a track's
volume), adds a new table at the end (a freshly recorded voice take), or removes a table (a take
that wasn't kept). Used by the studio server (server.py) and the song importer.
SRP/DRY check: Pass - the only code that writes to song files.
"""

import json
import re
from pathlib import Path


def _header_re(table: str):
    return re.compile(r"^\[" + re.escape(table) + r"\]\s*(#.*)?$")


def _block(lines, table):
    """(start, end) line indexes of a [table] block; end is the next table header or EOF."""
    head = _header_re(table)
    for i, line in enumerate(lines):
        if head.match(line.strip()):
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("["):
                j += 1
            # Leave trailing blank or comment lines with the next block.
            while j > i + 1 and (not lines[j - 1].strip() or lines[j - 1].lstrip().startswith("#")):
                j -= 1
            return i, j
    return None


def toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".") if value != int(value) else f"{value:.1f}"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value))   # JSON string quoting is valid TOML basic-string quoting


def set_value(path: Path, table: str, key: str, value):
    lines = Path(path).read_text().splitlines()
    block = _block(lines, table)
    if block is None:
        raise KeyError(f"no [{table}] in {Path(path).name}")
    start, end = block
    key_re = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    new_line = f"{key} = {toml_value(value)}"
    for i in range(start + 1, end):
        if key_re.match(lines[i]):
            lines[i] = new_line
            break
    else:
        lines.insert(end, new_line)
    Path(path).write_text("\n".join(lines) + "\n")


def add_table(path: Path, table: str, values: dict, comment: str = ""):
    text = Path(path).read_text().rstrip("\n")
    body = [f"[{table}]"] + [f"{k} = {toml_value(v)}" for k, v in values.items()]
    if comment:
        body.insert(0, f"# {comment}")
    Path(path).write_text(text + "\n\n" + "\n".join(body) + "\n")


def remove_table(path: Path, table: str):
    lines = Path(path).read_text().splitlines()
    block = _block(lines, table)
    if block is None:
        return
    start, end = block
    if start > 0 and lines[start - 1].lstrip().startswith("#"):
        start -= 1   # take the table's own comment line with it
    del lines[start:end]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    Path(path).write_text(text.rstrip("\n") + "\n")
