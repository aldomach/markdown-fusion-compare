"""
core/compare.py
Pure functions that determine the comparison status between two prop dicts.
No Qt dependencies.

Status codes (used as CSS object names in ui/styles.py):
  EQUAL          both sides identical
  DIFF           both sides exist, values differ
  WIKI_DIFF      both sides exist, same text but one is a wikilink
  LIST_PARTIAL   both sides are lists, some items overlap, some don't
  LEFT_ONLY      key exists only on the left
  RIGHT_ONLY     key exists only on the right
  EMPTY_DIFF     both sides exist, one or both are empty
"""

from __future__ import annotations
from core.utils import is_wikilink

# ── Status constants ──────────────────────────────────────────────────────────

EQUAL        = "equal"
DIFF         = "diff"
WIKI_DIFF    = "wiki_diff"
LIST_PARTIAL = "list_partial"
LEFT_ONLY    = "left_only"
RIGHT_ONLY   = "right_only"
EMPTY_DIFF   = "empty_diff"


def _strip_wiki(v: str) -> str:
    return v.strip().strip("[]")


def _normalise(val) -> str:
    """Flatten to lowercase plain string for loose comparison."""
    if isinstance(val, list):
        return "|".join(sorted(_strip_wiki(str(v)).lower() for v in val))
    return _strip_wiki(str(val)).lower()


def _is_empty(val) -> bool:
    if isinstance(val, list):
        return len(val) == 0
    return str(val).strip() == ""


def compare_values(left_val, right_val) -> str:
    """Return a status code for two values that both exist."""

    # Both empty
    if _is_empty(left_val) and _is_empty(right_val):
        return EQUAL

    # One empty
    if _is_empty(left_val) or _is_empty(right_val):
        return EMPTY_DIFF

    # List vs list
    if isinstance(left_val, list) and isinstance(right_val, list):
        ls = {_strip_wiki(v).lower() for v in left_val}
        rs = {_strip_wiki(v).lower() for v in right_val}
        if ls == rs:
            return EQUAL
        if ls & rs:          # some overlap
            return LIST_PARTIAL
        return DIFF

    # Scalar vs scalar (or mixed list/scalar — treat as diff)
    lv = str(left_val).strip()
    rv = str(right_val).strip()

    if lv == rv:
        return EQUAL

    # Same text, one is wikilink
    lplain = _strip_wiki(lv).lower()
    rplain = _strip_wiki(rv).lower()
    if lplain == rplain and (is_wikilink(lv) != is_wikilink(rv)):
        return WIKI_DIFF

    # Normalised equal (ignoring wikilink brackets on both)
    if lplain == rplain:
        return EQUAL

    return DIFF


def compare_props(
    left_props: dict,
    right_props: dict,
) -> dict[str, str]:
    """
    Return {key: status} for every key that appears in either dict.
    """
    all_keys = set(left_props) | set(right_props)
    result: dict[str, str] = {}

    for key in all_keys:
        in_left  = key in left_props
        in_right = key in right_props

        if in_left and not in_right:
            result[key] = LEFT_ONLY
        elif in_right and not in_left:
            result[key] = RIGHT_ONLY
        else:
            result[key] = compare_values(left_props[key], right_props[key])

    return result
