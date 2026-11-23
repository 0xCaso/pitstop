"""PreToolUse hook for twin arms: refuse any tool call that reaches outside the cycle's snapshot.

Env: TWIN_ALLOW (os.pathsep-separated roots the arm may touch), TWIN_GUARD_LOG (JSONL of refusals).
A refusal prints a PreToolUse deny decision; an allowed call prints nothing.
"""
import json
import os
import re
import sys
import time

# Absolute paths a command may name without leaving the snapshot: system tools and throwaway temp files.
SYSTEM = ("/usr/", "/bin/", "/sbin/", "/opt/homebrew/", "/System/", "/Library/Developer/", "/dev/null", "/dev/std",
          "/Applications/")
OUTWARD = re.compile(r"\b(?:git\s+push|gh\s+(?:pr|issue|release|api|repo)|npm\s+publish|curl|wget|ssh|scp|rsync)\b")
PATH_KEYS = ("file_path", "path", "notebook_path")
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\s*(?:\n|$)", re.DOTALL)
ABS_PATH = re.compile(r"(?<![\w.:/<>-])(?:~|/)[\w.@~][^\s'\"`;|&<>()]*")
UP_PATH = re.compile(r"(?<![\w.~/-])(?:[\w.@+-]+/)*\.\.(?:/[^\s'\"`;|&<>()]*)?")


def _inside(path, roots):
    real = os.path.realpath(os.path.expanduser(path))
    return any(real == r or real.startswith(r.rstrip("/") + "/") for r in roots)


def decide(tool, tool_input, roots, cwd=None):
    """The reason to refuse this call, or None to allow it."""
    if not isinstance(tool_input, dict):
        return None
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value and os.path.isabs(os.path.expanduser(value)) \
                and not _inside(value, roots):
            return "test run: %s is outside this session's files" % value
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        command = HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0] + "\n", command)  # text, not paths
        if OUTWARD.search(command):
            return "test run: no network, no push"
        for match in ABS_PATH.findall(command):
            if match.startswith(SYSTEM) or _inside(match, roots):
                continue
            return "test run: %s is outside this session's files" % match
        for match in UP_PATH.findall(command):
            if not _inside(os.path.join(cwd or os.getcwd(), match), roots):
                return "test run: %s is outside this session's files" % match
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    roots = [os.path.realpath(r) for r in os.environ.get("TWIN_ALLOW", "").split(os.pathsep) if r]
    reason = decide(event.get("tool_name"), event.get("tool_input"), roots, event.get("cwd"))
    if reason is None:
        return
    log = os.environ.get("TWIN_GUARD_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.time(), "tool": event.get("tool_name"), "input": event.get("tool_input"),
                                 "reason": reason}, ensure_ascii=False) + "\n")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


if __name__ == "__main__":
    main()
