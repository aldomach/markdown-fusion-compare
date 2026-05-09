"""
core/utils.py
Pure utility functions: wikilink conversion, value inspection, body deduplication.
No Qt dependencies.
"""

from datetime import datetime


# ── WikiLink helpers ──────────────────────────────────────────────────────────

def to_wikilink(value: str) -> str:
    """Wrap a plain string as a WikiLink: [[value]]."""
    val = value.strip().strip('"').strip("'").strip("[]")
    return f"[[{val}]]"


def is_wikilink(value: str) -> bool:
    v = value.strip()
    return v.startswith("[[") and v.endswith("]]")


def convert_value_to_wikilink(value) -> object:
    """Convert a prop value (str or list[str]) to wikilink form.
    Skips empty strings and already-wikilinked values.
    """
    if isinstance(value, list):
        return [
            to_wikilink(v) if (v.strip() and not is_wikilink(v)) else v
            for v in value
        ]
    sv = str(value).strip()
    if sv and not is_wikilink(sv):
        return to_wikilink(sv)
    return value


# ── Value inspection ──────────────────────────────────────────────────────────

def is_empty_value(value) -> bool:
    """True when value carries no meaningful content."""
    if isinstance(value, list):
        return len(value) == 0
    return str(value).strip() == ""


def display_value(value) -> str:
    """Short human-readable representation of a prop value."""
    if isinstance(value, list):
        if not value:
            return "(lista vacía)"
        return " | ".join(str(v) for v in value[:4]) + (" …" if len(value) > 4 else "")
    return str(value) if str(value).strip() != "" else "(vacío)"


def value_to_str(value) -> str:
    """Full string representation for display in dialogs/tables."""
    if isinstance(value, list):
        return " | ".join(str(v) for v in value) if value else "(vacío)"
    return str(value) if str(value).strip() else "(vacío)"


# ── Body helpers ──────────────────────────────────────────────────────────────

def body_lines_set(body: str) -> set[str]:
    """Non-empty, stripped lines of body — used for deduplication."""
    return {line.rstrip() for line in body.splitlines() if line.strip()}


def merge_body(src_body: str, dst_body: str, position: str) -> str:
    """Merge src lines not already in dst into dst at 'start' or 'end'."""
    dst_set = body_lines_set(dst_body)
    new_lines = [
        line for line in src_body.splitlines()
        if line.strip() and line.rstrip() not in dst_set
    ]
    if not new_lines:
        return dst_body

    added = "\n".join(new_lines)
    if position == "end":
        return (dst_body.rstrip() + "\n\n" + added).lstrip()
    else:
        return (added + "\n\n" + dst_body.lstrip()).rstrip()


def new_lines_preview(src_body: str, dst_body: str) -> list[str]:
    """Return lines from src that are not already in dst."""
    dst_set = body_lines_set(dst_body)
    return [
        line for line in src_body.splitlines()
        if line.strip() and line.rstrip() not in dst_set
    ]


# ── Timestamp ─────────────────────────────────────────────────────────────────

def now_timestamp() -> str:
    """Return current datetime in Obsidian-compatible format: YYYY-MM-DDTHH:MM"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M")
