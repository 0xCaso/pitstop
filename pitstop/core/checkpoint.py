"""What a checkpoint holds, in numbers, and whether the files it cites under Re-read exist."""
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

CHAT_TEXT = "Chat-only text"
REREAD = "Re-read"
# The section titles of the checkpoint template in SKILL.md, in English in every language.
TEMPLATE_TITLES = frozenset({"Goal", "Current state", "Next action", CHAT_TEXT, "Decisions made", "User preferences",
                             "Discarded", REREAD, "Unsaved or uncommitted work", "Open questions", "Suggested skills"})
EMPTY = "—"
_BACKTICKS = re.compile(r"`([^`]+)`")
# Between two paths of one entry: a comma, a semicolon, "and", "e" or "&".
_SEPARATOR = re.compile(r"^\s*(,|;|&|\band\b|\be\b)?\s*")
_LINE_SUFFIX = re.compile(r":\d+(-\d+)?$")
_PATTERN_CHARS = set("*?{}[]<>")


@dataclass(frozen=True)
class CheckpointStats:
    bytes: int
    sections_filled: int
    chat_text_filled: bool
    support_files: int
    missing: List[str]
    unchecked: List[str]


def _sections(text: str) -> Dict[str, str]:
    """`## <title>` -> body. A later section with the same title wins. Lines inside ``` fences are body. Once a
    template title has been seen, only template titles start a section: a heading pasted into Chat-only text
    stays in its body. Checkpoints with no template title (older ones, titles in another language) split on
    every `## ` line."""
    sections: Dict[str, str] = {}
    title = None
    body: List[str] = []
    fenced = templated = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        heading = line[3:].strip() if line.startswith("## ") and not fenced else None
        if heading is not None and (heading in TEMPLATE_TITLES or not templated):
            if title is not None:
                sections[title] = "\n".join(body)
            title, body = heading, []
            templated = templated or heading in TEMPLATE_TITLES
        elif title is not None:
            body.append(line)
    if title is not None:
        sections[title] = "\n".join(body)
    return sections


def _filled(body: str) -> bool:
    stripped = body.strip()
    return bool(stripped) and stripped != EMPTY


def _resolve(path: str, cwd: str) -> str:
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.join(cwd, path)


def _check_path(cited: str, cwd: str) -> str:
    """"ok", "missing" or "unchecked" for one cited path."""
    if "://" in cited or _PATTERN_CHARS & set(cited):
        return "unchecked"
    path = _resolve(_LINE_SUFFIX.sub("", cited), cwd)
    if os.path.exists(path):
        return "ok"
    # A folder that does not exist either: an alias or another checkout, not a typo to block on.
    return "missing" if os.path.isdir(os.path.dirname(os.path.normpath(path))) else "unchecked"


def _leading_paths(entry: str) -> List[str]:
    """The backticked paths an entry starts with (`a`, `b` and `c` — why): the reason after them may name code."""
    paths = []
    rest = entry
    while True:
        match = _BACKTICKS.match(rest)
        if match is None:
            return paths
        paths.append(match.group(1).strip())
        rest = _SEPARATOR.sub("", rest[match.end():], count=1)


def _check_entry(entry: str, cwd: str) -> Tuple[List[str], bool]:
    """The missing paths of one Re-read line (without its leading "- "), and whether any part was left unchecked."""
    paths = _leading_paths(entry) if "origin/" not in entry else []
    if not paths:
        return [], True
    results = [(path, _check_path(path, cwd)) for path in paths]
    return [path for path, result in results if result == "missing"], any(r == "unchecked" for _, r in results)


def _in_folder(path: str, folder: str) -> bool:
    return os.path.realpath(os.path.dirname(path)) == os.path.realpath(folder)


def analyze_checkpoint(text: str, cwd: str, support_dir: str) -> CheckpointStats:
    """support_dir: where support files live (next to the checkpoint); files cited elsewhere are not counted."""
    sections = _sections(text)
    chat = sections.get(CHAT_TEXT, "")
    cited = (_resolve(_LINE_SUFFIX.sub("", path.strip()), cwd) for path in _BACKTICKS.findall(chat))
    support = sum(1 for path in cited if os.path.isfile(path) and _in_folder(path, support_dir))
    missing: List[str] = []
    unchecked: List[str] = []
    for line in sections.get(REREAD, "").splitlines():
        if not line.startswith("- "):
            continue
        entry = line[2:].strip()
        if not entry or entry == EMPTY:
            continue
        lost, partly_unchecked = _check_entry(entry, cwd)
        missing.extend(lost)
        if partly_unchecked and not lost:
            unchecked.append(entry)
    return CheckpointStats(
        bytes=len(text.encode("utf-8")),
        sections_filled=sum(1 for body in sections.values() if _filled(body)),
        chat_text_filled=_filled(chat),
        support_files=support,
        missing=missing,
        unchecked=unchecked,
    )
