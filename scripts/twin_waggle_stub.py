"""Stub Waggle MCP server for twin arms: records each call and answers that no human is there.

Stdio JSON-RPC, one message per line. Env: TWIN_WAGGLE_LOG (JSONL of calls). Registered as server
`plugin_waggle_waggle`, so the tool names match the real plugin's.
"""
import json
import os
import sys
import time
import uuid

TOOLS = {
    "waggle_ask": "Ask the human a decision or a review.",
    "waggle_check": "Check a case for the human's reply.",
    "waggle_update": "Send an update on an open case.",
    "waggle_guide": "Guidance on asks, artifacts and replies.",
}
PENDING = "TEST RUN: the ask was recorded. No human answers in this run; carry on with work that does not depend on it."


def reply(call_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": call_id, "result": result}) + "\n")
    sys.stdout.flush()


def handle(message):
    method, call_id = message.get("method"), message.get("id")
    if call_id is None:
        return  # a notification
    if method == "initialize":
        reply(call_id, {"protocolVersion": (message.get("params") or {}).get("protocolVersion", "2025-06-18"),
                        "capabilities": {"tools": {}}, "serverInfo": {"name": "waggle-stub", "version": "0"}})
    elif method == "tools/list":
        reply(call_id, {"tools": [{"name": name, "description": text,
                                   "inputSchema": {"type": "object", "additionalProperties": True}}
                                  for name, text in TOOLS.items()]})
    elif method == "tools/call":
        params = message.get("params") or {}
        args = params.get("arguments") or {}
        case = args.get("case_id") or args.get("follows") or "c_%s" % uuid.uuid4()
        log = os.environ.get("TWIN_WAGGLE_LOG")
        if log:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": time.time(), "tool": params.get("name"), "arguments": args},
                                    ensure_ascii=False) + "\n")
        text = json.dumps({"case_id": case, "status": "pending", "note": PENDING})
        reply(call_id, {"content": [{"type": "text", "text": text}]})
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": call_id,
                                     "error": {"code": -32601, "message": "unknown method"}}) + "\n")
        sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if isinstance(message, dict):
            handle(message)


if __name__ == "__main__":
    main()
