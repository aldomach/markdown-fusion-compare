"""
core/yaml_parser.py
Pure functions for parsing and serializing Obsidian-flavoured YAML frontmatter.
No Qt dependencies.
"""


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text.
    Returns (props_dict, body_text).
    """
    props: dict = {}
    body: str = text

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            yaml_block = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            props = _parse_yaml(yaml_block)

    return props, body


def serialize_frontmatter(props: dict, body: str) -> str:
    """Serialize props dict + body back to a markdown string."""
    if not props and not body.strip():
        return ""

    lines = ["---"]
    for key, val in props.items():
        if isinstance(val, list):
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")

    if body.strip():
        lines.append("")
        lines.append(body.rstrip())

    return "\n".join(lines) + "\n"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_yaml(yaml_text: str) -> dict:
    result: dict = {}
    lines = yaml_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()

            if val == "":
                # Collect list items on subsequent indented lines
                items: list[str] = []
                i += 1
                while i < len(lines) and (
                    lines[i].startswith("  ") or lines[i].startswith("- ")
                ):
                    item_line = lines[i].strip()
                    if item_line.startswith("- "):
                        items.append(item_line[2:].strip())
                    i += 1
                result[key] = items if items else ""
                continue
            else:
                result[key] = val

        i += 1

    return result
