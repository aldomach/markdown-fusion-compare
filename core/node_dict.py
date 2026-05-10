"""
core/node_dict.py
NodeDictionary: persistent dictionary of known nodes (WikiLink targets)
and a blacklist of words/phrases to never convert.

Storage: two JSON files next to the script, in the user's config dir.
  nodes.json     — accepted nodes (str list)
  blacklist.json — ignored words/phrases (str list)

Features:
  - Single-word and multi-word phrase nodes
  - Blacklist overrides everything
  - Connectors/prepositions optional filter
  - find_candidates(left_body, right_body, min_len, use_stopwords)
      → returns CandidateResult with single-word and multi-word matches
  - apply_nodes(body, nodes) → body with [[node]] replacements
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ── Stop-words (Spanish + English connectors / prepositions) ─────────────────

STOP_WORDS_ES = {
    "de", "la", "el", "en", "un", "es", "se", "no", "si", "lo",
    "que", "los", "las", "del", "una", "por", "con", "para", "pero",
    "como", "más", "este", "esta", "esto", "son", "sus", "fue",
    "ser", "han", "hay", "al", "ya", "le", "me", "mi", "tu", "su",
    "nos", "les", "muy", "bien", "también", "sobre", "entre", "sin",
    "hasta", "desde", "hacia", "ante", "bajo", "tras", "según",
    "durante", "mediante", "versus", "via",
}

STOP_WORDS_EN = {
    "the", "and", "for", "are", "was", "with", "that", "this",
    "from", "have", "not", "also", "its", "into", "been", "has",
    "will", "can", "but", "they", "she", "his", "her", "our",
    "their", "which", "when", "where", "who", "what", "how",
    "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "than", "then", "there", "these", "those",
    "through", "about", "above", "after", "before", "between",
    "into", "during", "without", "within", "along", "across",
}

ALL_STOP_WORDS: set[str] = STOP_WORDS_ES | STOP_WORDS_EN

_STRIP_CHARS = ' \t\n\r.,;:!?()[]{}"\'-–—#*_`~^<>/\\|@'


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CandidateResult:
    single_words:  list[str] = field(default_factory=list)  # single tokens in both bodies
    multi_phrases: list[str] = field(default_factory=list)  # multi-word phrases in both bodies
    from_dict:     list[str] = field(default_factory=list)  # dict entries found in both bodies

    @property
    def all_candidates(self) -> list[str]:
        """Deduplicated, sorted list of all candidates."""
        seen: set[str] = set()
        result: list[str] = []
        for item in self.from_dict + self.multi_phrases + self.single_words:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return sorted(result, key=str.lower)


# ── Persistence helpers ───────────────────────────────────────────────────────

def _default_path(filename: str) -> Path:
    """Store data files next to this module's package root."""
    base = Path(__file__).parent.parent  # project root
    return base / "data" / filename


def _load_list(path: Path) -> list[str]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_list(path: Path, items: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(set(items), key=str.lower), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Core class ────────────────────────────────────────────────────────────────

class NodeDictionary:
    """
    Manages the node dictionary and blacklist.
    All mutations are immediately persisted to disk.
    """

    def __init__(
        self,
        nodes_path:     Path | None = None,
        blacklist_path: Path | None = None,
    ):
        self._nodes_path     = nodes_path     or _default_path("nodes.json")
        self._blacklist_path = blacklist_path or _default_path("blacklist.json")
        self._nodes:     list[str] = _load_list(self._nodes_path)
        self._blacklist: list[str] = _load_list(self._blacklist_path)

    # ── Accessors ─────────────────────────────────────────────────────────

    @property
    def nodes(self) -> list[str]:
        return list(self._nodes)

    @property
    def blacklist(self) -> list[str]:
        return list(self._blacklist)

    # ── Nodes ─────────────────────────────────────────────────────────────

    def add_node(self, node: str) -> bool:
        """Add a node. Returns True if added (False if already present)."""
        node = node.strip()
        if not node:
            return False
        if any(n.lower() == node.lower() for n in self._nodes):
            return False
        self._nodes.append(node)
        self._save_nodes()
        return True

    def add_nodes(self, nodes: Iterable[str]) -> int:
        """Add multiple nodes. Returns count added."""
        count = 0
        for n in nodes:
            if self.add_node(n):
                count += 1
        return count

    def remove_node(self, node: str) -> bool:
        before = len(self._nodes)
        self._nodes = [n for n in self._nodes if n.lower() != node.lower()]
        if len(self._nodes) < before:
            self._save_nodes()
            return True
        return False

    def clear_nodes(self) -> None:
        self._nodes = []
        self._save_nodes()

    # ── Blacklist ─────────────────────────────────────────────────────────

    def add_blacklist(self, word: str) -> bool:
        word = word.strip()
        if not word:
            return False
        if any(w.lower() == word.lower() for w in self._blacklist):
            return False
        self._blacklist.append(word)
        self._save_blacklist()
        return True

    def remove_blacklist(self, word: str) -> bool:
        before = len(self._blacklist)
        self._blacklist = [w for w in self._blacklist if w.lower() != word.lower()]
        if len(self._blacklist) < before:
            self._save_blacklist()
            return True
        return False

    def clear_blacklist(self) -> None:
        self._blacklist = []
        self._save_blacklist()

    def is_blacklisted(self, text: str) -> bool:
        tl = text.lower()
        return any(w.lower() == tl for w in self._blacklist)

    # ── Candidate detection ───────────────────────────────────────────────

    def find_candidates(
        self,
        left_body:      str,
        right_body:     str,
        min_len:        int  = 4,
        use_stopwords:  bool = True,
        whole_word:     bool = True,
    ) -> CandidateResult:
        """
        Find words/phrases common to both bodies.

        Rules:
          - Every individual token in a phrase must have >= min_len
            ALPHANUMERIC characters (spaces don't count toward min_len)
          - If use_stopwords=True, any token that is a stop-word disqualifies
            the entire phrase (single words) or the token itself (multi-word:
            stop-words are allowed inside phrases but the phrase must contain
            at least one non-stop-word token that meets min_len)
          - whole_word=True: matches only at word boundaries
          - Blacklisted entries are excluded at all levels
          - Priority: dict entries > multi-word phrases > single words
        """
        result = CandidateResult()

        # 1. Dict entries present in both bodies
        for node in self._nodes:
            if self.is_blacklisted(node):
                continue
            if _phrase_in_body(node, left_body, whole_word) and \
               _phrase_in_body(node, right_body, whole_word):
                result.from_dict.append(node)

        # 2. Multi-word phrases common to both (token-level validation)
        left_phrases  = _extract_phrases(left_body,  max_n=4,
                                          min_len=min_len,
                                          use_stopwords=use_stopwords)
        right_phrases = _extract_phrases(right_body, max_n=4,
                                          min_len=min_len,
                                          use_stopwords=use_stopwords)
        common_phrases = left_phrases & right_phrases

        for phrase in sorted(common_phrases, key=lambda p: (-len(p.split()), p.lower())):
            if self.is_blacklisted(phrase):
                continue
            already = any(
                phrase.lower() in e.lower()
                for e in result.multi_phrases + result.from_dict
            )
            if not already:
                result.multi_phrases.append(phrase)

        # 3. Single words (each token must meet min_len on its own)
        left_words  = _tokenise(left_body,  min_len, use_stopwords)
        right_words = _tokenise(right_body, min_len, use_stopwords)
        common_words = left_words & right_words

        for word in sorted(common_words):
            if self.is_blacklisted(word):
                continue
            covered = any(
                word.lower() in p.lower()
                for p in result.from_dict + result.multi_phrases
            )
            if not covered:
                result.single_words.append(word)

        return result

    # ── Apply ─────────────────────────────────────────────────────────────

    def apply_nodes_to_body(self, body: str, nodes: list[str]) -> str:
        """
        Replace occurrences of each node in body with [[node]].
        Longer phrases are replaced before shorter words to avoid
        partial replacements (e.g. 'Juan Carlos' before 'Juan').
        Skips text already inside [[ ]].
        """
        # Sort longest first
        ordered = sorted(nodes, key=lambda n: (-len(n), n.lower()))
        result  = body
        for node in ordered:
            if self.is_blacklisted(node):
                continue
            pattern = re.compile(
                r'(?<!\[)(?<!\w)' + re.escape(node) + r'(?!\w)(?!\])',
                re.IGNORECASE,
            )
            result = pattern.sub(f"[[{node}]]", result)
        return result

    # ── Persistence ───────────────────────────────────────────────────────

    def _save_nodes(self)     -> None: _save_list(self._nodes_path,     self._nodes)
    def _save_blacklist(self) -> None: _save_list(self._blacklist_path, self._blacklist)


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _tokenise(text: str, min_len: int, use_stopwords: bool) -> set[str]:
    """Extract single words. min_len counts only alphanumeric chars."""
    words: set[str] = set()
    for raw in text.split():
        word = raw.strip(_STRIP_CHARS).lower()
        alnum_len = sum(1 for c in word if c.isalnum())
        if (
            not word
            or alnum_len < min_len
            or word.isdigit()
            or word.startswith("[[")
        ):
            continue
        if use_stopwords and word in ALL_STOP_WORDS:
            continue
        words.add(word)
    return words


def _extract_phrases(
    text:         str,
    max_n:        int  = 4,
    min_len:      int  = 4,
    use_stopwords: bool = True,
) -> set[str]:
    """
    Extract 2..max_n word phrases from text.

    Token-level rules:
      - Each token must have >= min_len ALPHANUMERIC characters
      - If use_stopwords=True, tokens that are stop-words are excluded;
        a phrase where ALL tokens are stop-words is rejected
      - The phrase must contain at least one token that passes min_len
        AND is not a stop-word
    """
    # Build validated token list preserving original case
    tokens: list[str] = []
    for raw in text.split():
        t = raw.strip(_STRIP_CHARS)
        if not t or t.isdigit() or t.startswith("[["):
            continue
        alnum_len = sum(1 for c in t if c.isalnum())
        if alnum_len < min_len:
            continue
        tokens.append(t)

    phrases: set[str] = set()
    for n in range(2, max_n + 1):
        for i in range(len(tokens) - n + 1):
            chunk = tokens[i:i + n]
            chunk_lower = [t.lower() for t in chunk]

            if use_stopwords:
                # Reject if any token is a stop-word without a valid anchor
                has_valid = any(
                    t not in ALL_STOP_WORDS and
                    sum(1 for c in t if c.isalnum()) >= min_len
                    for t in chunk_lower
                )
                if not has_valid:
                    continue
                # Also reject phrases that START or END with a stop-word
                if chunk_lower[0] in ALL_STOP_WORDS or chunk_lower[-1] in ALL_STOP_WORDS:
                    continue

            phrases.add(" ".join(chunk))
    return phrases


def _phrase_in_body(phrase: str, body: str, whole_word: bool = True) -> bool:
    """Case-insensitive search. whole_word=True uses word boundaries."""
    if whole_word:
        pattern = r'(?<!\w)' + re.escape(phrase) + r'(?!\w)'
    else:
        pattern = re.escape(phrase)
    return bool(re.search(pattern, body, re.IGNORECASE))
