"""
core/models.py
NoteFile: holds props + body for one markdown file, with undo history.
No Qt dependencies.
"""

from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Optional

from core.yaml_parser import parse_frontmatter, serialize_frontmatter


MAX_HISTORY = 50  # maximum undo steps


@dataclass
class NoteState:
    """Immutable snapshot of props + body at one point in time."""
    props: dict
    body: str


class NoteFile:
    """
    Represents one loaded (or new) markdown file.
    Tracks the current props/body and a stack of previous states for undo.
    """

    def __init__(self, filepath: Optional[str] = None):
        self.filepath: Optional[str] = filepath
        self._props: dict = {}
        self._body: str = ""
        self._history: list[NoteState] = []   # undo stack (oldest → newest)
        self._dirty: bool = False              # unsaved changes flag

    # ── Accessors ─────────────────────────────────────────────────────────

    @property
    def props(self) -> dict:
        return self._props

    @property
    def body(self) -> str:
        return self._body

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def can_undo(self) -> bool:
        return len(self._history) > 0

    # ── Load / Save ───────────────────────────────────────────────────────

    def load(self, filepath: str) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        self.filepath = filepath
        props, body = parse_frontmatter(content)
        self._props = props
        self._body = body
        self._history.clear()
        self._dirty = False

    def save(self, filepath: Optional[str] = None) -> str:
        """Write to disk. Returns the path used."""
        target = filepath or self.filepath
        if not target:
            raise ValueError("No filepath specified")
        self.filepath = target
        content = serialize_frontmatter(self._props, self._body)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        self._dirty = False
        return target

    def new_empty(self) -> None:
        """Reset to a blank in-memory file."""
        self._props = {}
        self._body = ""
        self._history.clear()
        self._dirty = False
        self.filepath = None

    # ── Mutation (always push history first) ──────────────────────────────

    def _push_history(self) -> None:
        snapshot = NoteState(
            props=copy.deepcopy(self._props),
            body=self._body,
        )
        self._history.append(snapshot)
        if len(self._history) > MAX_HISTORY:
            self._history.pop(0)
        self._dirty = True

    def set_prop(self, key: str, value) -> None:
        self._push_history()
        self._props[key] = value

    def add_to_list_prop(self, key: str, value) -> None:
        self._push_history()
        current = self._props.get(key, [])
        if isinstance(current, list):
            if value not in current:
                current = current + [value]
        else:
            current = [value] if current == "" else (
                [current, value] if current != value else [current]
            )
        self._props[key] = current

    def set_prop_empty(self, key: str) -> None:
        """Set a prop to empty string (key present, no value)."""
        self._push_history()
        self._props[key] = ""

    def delete_prop(self, key: str) -> None:
        if key not in self._props:
            return
        self._push_history()
        del self._props[key]

    def rename_prop(self, old_key: str, new_key: str) -> None:
        if old_key not in self._props or old_key == new_key:
            return
        self._push_history()
        val = self._props.pop(old_key)
        self._props[new_key] = val

    def convert_prop_to_wikilink(self, key: str) -> None:
        from core.utils import convert_value_to_wikilink, is_empty_value
        val = self._props.get(key)
        if val is None or is_empty_value(val):
            return
        new_val = convert_value_to_wikilink(val)
        if new_val != val:
            self._push_history()
            self._props[key] = new_val

    def set_body(self, body: str) -> None:
        self._push_history()
        self._body = body

    def set_body_silent(self, body: str) -> None:
        """Update body WITHOUT pushing to history.
        Used for debounced editor sync — avoids recording every keystroke.
        Call checkpoint() after a meaningful pause to save a real undo point.
        """
        self._body = body
        self._dirty = True

    def checkpoint(self) -> None:
        """Push current state to history as an undo point.
        Called by the editor after a debounce delay (e.g. 800ms of inactivity).
        """
        self._push_history()

    def set_props_and_body(self, props: dict, body: str) -> None:
        """Bulk replace — used when user edits raw text."""
        self._push_history()
        self._props = props
        self._body = body

    # ── Undo ──────────────────────────────────────────────────────────────

    def undo(self) -> bool:
        """Revert to previous state. Returns True if successful."""
        if not self._history:
            return False
        snap = self._history.pop()
        self._props = snap.props
        self._body = snap.body
        self._dirty = True
        return True

    # ── Helpers ───────────────────────────────────────────────────────────

    def sorted_keys(self) -> list[str]:
        return sorted(self._props.keys(), key=str.lower)

    def to_markdown(self) -> str:
        return serialize_frontmatter(self._props, self._body)
