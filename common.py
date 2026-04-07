"""Shared protocol helpers for the TCP chat application.

The app uses newline-delimited JSON messages so the server and client can
exchange structured data over a plain TCP socket without extra dependencies.
"""

from __future__ import annotations

import json
import socket
from typing import Any, Dict


def send_json(sock: socket.socket, payload: Dict[str, Any]) -> None:
    """Send one JSON message followed by a newline."""

    message = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    sock.sendall((message + "\n").encode("utf-8"))


def safe_json_loads(raw_line: str) -> Dict[str, Any] | None:
    """Parse a JSON line and return None if it is invalid."""

    try:
        parsed = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return parsed
    return None
