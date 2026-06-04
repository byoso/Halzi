import re
from html import escape


KEYWORD_COLOR = "#d73a49"
STRING_COLOR = "#032f62"
NUMBER_COLOR = "#005cc5"
COMMENT_COLOR = "#6a737d"
INLINE_CODE_COLOR = "#6f42c1"

LANGUAGE_KEYWORDS = {
    "python": {
        "and", "as", "assert", "async", "await", "break", "class", "continue",
        "def", "del", "elif", "else", "except", "False", "finally", "for", "from",
        "global", "if", "import", "in", "is", "lambda", "None", "nonlocal", "not",
        "or", "pass", "raise", "return", "True", "try", "while", "with", "yield",
    },
    "javascript": {
        "await", "break", "case", "catch", "class", "const", "continue", "debugger",
        "default", "delete", "do", "else", "export", "extends", "false", "finally",
        "for", "function", "if", "import", "in", "instanceof", "let", "new", "null",
        "return", "super", "switch", "this", "throw", "true", "try", "typeof", "var",
        "void", "while", "with", "yield",
    },
    "typescript": {
        "any", "as", "async", "await", "boolean", "break", "case", "catch", "class",
        "const", "continue", "debugger", "default", "delete", "do", "else", "enum",
        "export", "extends", "false", "finally", "for", "function", "if", "implements",
        "import", "in", "instanceof", "interface", "let", "module", "new", "null",
        "number", "private", "protected", "public", "readonly", "return", "static",
        "string", "super", "switch", "this", "throw", "true", "try", "type", "typeof",
        "undefined", "var", "void", "while", "with", "yield",
    },
    "json": {"true", "false", "null"},
    "bash": {
        "if", "then", "else", "elif", "fi", "for", "in", "do", "done", "case", "esac",
        "while", "until", "function", "return", "export", "local", "readonly", "unset",
    },
}


def markdown_to_pango(text: str) -> str:
    """Convert a lightweight Markdown subset to Pango markup.

    Supported:
    - headings (#, ##, ###)
    - unordered lists (-, *)
    - bold (**text**)
    - italic (*text*)
    - inline code (`code`)
    - fenced code blocks (```)
    """
    if not text:
        return ""

    # Drop control characters that can break Pango markup parsing.
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    lines = text.splitlines()
    out_lines = []
    in_code_block = False
    code_language = ""
    i = 0

    while i < len(lines):
        line = lines[i]
        fence_match = re.match(r"^\s*```\s*([A-Za-z0-9_+-]+)?\s*$", line)
        if fence_match:
            in_code_block = not in_code_block
            if in_code_block:
                code_language = (fence_match.group(1) or "").lower()
            else:
                code_language = ""
            i += 1
            continue

        if in_code_block:
            out_lines.append(_highlight_code_line(line, code_language))
            i += 1
            continue

        if i + 1 < len(lines) and _is_table_row(lines[i]) and _is_table_separator(lines[i + 1]):
            table_lines = [lines[i], lines[i + 1]]
            j = i + 2
            while j < len(lines) and _is_table_row(lines[j]):
                table_lines.append(lines[j])
                j += 1
            out_lines.extend(_table_to_markup_lines(table_lines))
            i = j
            continue

        line_markup = _line_to_markup(line)
        out_lines.append(line_markup)
        i += 1

    return "\n".join(out_lines)


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False
    cells = _split_table_cells(stripped)
    return len(cells) >= 2


def _is_table_separator(line: str) -> bool:
    cells = _split_table_cells(line.strip())
    if not cells:
        return False
    for cell in cells:
        if not re.match(r"^:?-{3,}:?$", cell.strip()):
            return False
    return True


def _split_table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _table_to_markup_lines(lines: list[str]) -> list[str]:
    rows = [_split_table_cells(line) for line in lines]
    if len(rows) < 2:
        return [_inline_markdown_to_pango(line) for line in lines]

    data_rows = [rows[0]] + rows[2:]
    col_count = max((len(row) for row in data_rows), default=0)
    if col_count == 0:
        return []

    widths = [0] * col_count
    for row in data_rows:
        for idx in range(col_count):
            value = row[idx] if idx < len(row) else ""
            widths[idx] = max(widths[idx], len(value))

    out = []
    out.append(_table_row_to_tt(rows[0], widths))
    out.append(_table_separator_to_tt(widths))
    for row in rows[2:]:
        out.append(_table_row_to_tt(row, widths))
    return out


def _table_row_to_tt(row: list[str], widths: list[int]) -> str:
    padded = []
    for idx, width in enumerate(widths):
        value = row[idx] if idx < len(row) else ""
        padded.append(value.ljust(width))
    raw = "| " + " | ".join(padded) + " |"
    return f"<tt>{escape(raw)}</tt>"


def _table_separator_to_tt(widths: list[int]) -> str:
    raw = "|-" + "-|-".join("-" * width for width in widths) + "-|"
    return f"<tt>{escape(raw)}</tt>"


def _line_to_markup(line: str) -> str:
    stripped = line.lstrip()

    heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
    if heading_match is not None:
        body = _inline_markdown_to_pango(heading_match.group(2))
        return f"<b>{body}</b>"

    if stripped.startswith("- ") or stripped.startswith("* "):
        body = _inline_markdown_to_pango(stripped[2:])
        return f"• {body}"

    return _inline_markdown_to_pango(line)


def _inline_markdown_to_pango(text: str) -> str:
    escaped = escape(text)

    # Inline code first to avoid formatting inside code spans.
    escaped = re.sub(
        r"`([^`]+)`",
        lambda m: f"<tt><span foreground=\"{INLINE_CODE_COLOR}\">{m.group(1)}</span></tt>",
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)

    return escaped


def _highlight_code_line(line: str, language: str) -> str:
    comment_start = _comment_prefix(language)
    comment_index = -1
    if comment_start:
        comment_index = line.find(comment_start)

    if comment_index >= 0:
        code_part = line[:comment_index]
        comment_part = line[comment_index:]
    else:
        code_part = line
        comment_part = ""

    highlighted = _highlight_code_part(code_part, language)
    if comment_part:
        highlighted += _span(escape(comment_part), COMMENT_COLOR)

    return f"<tt>{highlighted}</tt>"


def _highlight_code_part(code: str, language: str) -> str:
    if not code:
        return ""

    tokens = []
    pattern = re.compile(r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')")
    pos = 0
    for match in pattern.finditer(code):
        if match.start() > pos:
            tokens.append(("plain", code[pos:match.start()]))
        tokens.append(("string", match.group(0)))
        pos = match.end()
    if pos < len(code):
        tokens.append(("plain", code[pos:]))

    out = []
    for token_type, token_value in tokens:
        if token_type == "string":
            out.append(_span(escape(token_value), STRING_COLOR))
        else:
            out.append(_highlight_plain_code(token_value, language))
    return "".join(out)


def _highlight_plain_code(text: str, language: str) -> str:
    escaped = escape(text)
    keywords = LANGUAGE_KEYWORDS.get(language, LANGUAGE_KEYWORDS.get(_normalize_language(language), set()))
    if keywords:
        keyword_pattern = r"\\b(" + "|".join(sorted(re.escape(k) for k in keywords)) + r")\\b"
        escaped = re.sub(keyword_pattern, lambda m: _span(m.group(1), KEYWORD_COLOR), escaped)

    escaped = re.sub(
        r"\\b\\d+(?:\\.\\d+)?\\b",
        lambda m: _span(m.group(0), NUMBER_COLOR),
        escaped,
    )
    return escaped


def _comment_prefix(language: str) -> str:
    lang = _normalize_language(language)
    if lang in {"python", "bash", "shell"}:
        return "#"
    if lang in {"javascript", "typescript", "json", "c", "cpp", "java", "go", "rust"}:
        return "//"
    return ""


def _normalize_language(language: str) -> str:
    aliases = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "sh": "bash",
        "zsh": "bash",
        "yml": "yaml",
    }
    return aliases.get(language.lower(), language.lower())


def _span(content: str, color: str) -> str:
    return f"<span foreground=\"{color}\">{content}</span>"
