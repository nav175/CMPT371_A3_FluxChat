"""Browser-based GUI client for the CMPT 371 socket chat assignment.

This client runs a local Flask app that serves a polished web interface.
The backend maintains a real TCP socket connection to the chat server and
bridges server events to the browser through lightweight polling APIs.
"""

from __future__ import annotations

import argparse
import socket
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from common import safe_json_loads, send_json


DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 5050
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000

WEB_DIR = Path(__file__).resolve().parent / "web"


class ChatSession:
    """Manage one TCP chat connection and expose event snapshots for the UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._socket_file: Any = None
        self._receiver_thread: threading.Thread | None = None
        self._running = False
        self._connected = False
        self._host = ""
        self._port = 0
        self._username = ""
        self._users: list[str] = []
        self._events: list[dict[str, Any]] = []
        self._next_event_id = 1

    def connect(self, host: str, port: int, username: str) -> tuple[bool, str | None]:
        host = host.strip()
        username = username.strip()
        if not host or not username:
            return False, "Host and username are required."

        with self._lock:
            if self._connected:
                return False, "Already connected. Disconnect first."

        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock_file = sock.makefile("r", encoding="utf-8", newline="\n")
            sock.settimeout(5)
            send_json(sock, {"type": "join", "username": username})
            first_raw = sock_file.readline()
        except OSError as exc:
            return False, f"Could not connect to {host}:{port}. {exc}"

        first_message = safe_json_loads(first_raw) if first_raw else None
        if not first_message:
            try:
                sock.close()
            except OSError:
                pass
            return False, "The server did not return a valid response."

        if first_message.get("type") == "error":
            try:
                sock.close()
            except OSError:
                pass
            return False, str(first_message.get("message", "Server rejected the connection."))

        sock.settimeout(None)

        with self._lock:
            self._socket = sock
            self._socket_file = sock_file
            self._host = host
            self._port = port
            self._username = username
            self._connected = True
            self._running = True
            self._users = []
            self._append_event_locked(
                kind="system",
                text=f"Connected to {host}:{port} as {username}.",
            )

        self._handle_message(first_message)
        self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._receiver_thread.start()
        self.send({"type": "list"})
        return True, None

    def disconnect(self) -> None:
        with self._lock:
            sock = self._socket
            is_connected = self._connected

        if not is_connected:
            return

        if sock is not None:
            try:
                send_json(sock, {"type": "quit"})
            except OSError:
                pass

        self._finalize_disconnect("Disconnected from server.")

    def send_user_input(self, text: str, recipient: str) -> tuple[bool, str | None]:
        text = text.strip()
        if not text:
            return False, "Message cannot be empty."

        if text == "/help":
            self._append_event(
                kind="system",
                text="Commands: /help, /list, /msg <user> <text>, /quit",
            )
            return True, None

        if text == "/list":
            return self.send({"type": "list"})

        if text == "/quit":
            self.disconnect()
            return True, None

        if text.startswith("/msg "):
            _, _, remainder = text.partition(" ")
            target, _, message_text = remainder.partition(" ")
            if not target or not message_text:
                return False, "Usage: /msg <user> <text>"
            target = target.strip()
            message_text = message_text.strip()
            ok, error = self.send({"type": "private", "target": target, "text": message_text})
            if ok:
                self._append_event(
                    kind="chat",
                    text=message_text,
                    sender=f"{self._username} -> {target}",
                    scope="private",
                )
            return ok, error

        selected = recipient.strip()
        if selected and selected != "Everyone":
            ok, error = self.send({"type": "private", "target": selected, "text": text})
            if ok:
                self._append_event(
                    kind="chat",
                    text=text,
                    sender=f"{self._username} -> {selected}",
                    scope="private",
                )
            return ok, error
        return self.send({"type": "chat", "text": text})

    def send(self, payload: dict[str, object]) -> tuple[bool, str | None]:
        with self._lock:
            sock = self._socket
            is_connected = self._connected

        if not is_connected or sock is None:
            return False, "Not connected."

        try:
            send_json(sock, payload)
        except OSError:
            self._finalize_disconnect("Connection to server was lost.")
            return False, "Connection to server was lost."

        return True, None

    def snapshot(self, after_event_id: int = 0) -> dict[str, Any]:
        with self._lock:
            events = [event for event in self._events if event["id"] > after_event_id]
            return {
                "connected": self._connected,
                "host": self._host,
                "port": self._port,
                "username": self._username,
                "users": list(self._users),
                "events": events,
                "lastEventId": self._events[-1]["id"] if self._events else 0,
            }

    def _receive_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    return
                socket_file = self._socket_file

            if socket_file is None:
                return

            try:
                raw_line = socket_file.readline()
            except OSError:
                self._finalize_disconnect("Connection to server was interrupted.")
                return

            if not raw_line:
                self._finalize_disconnect("Server closed the connection.")
                return

            message = safe_json_loads(raw_line)
            if message is None:
                continue
            self._handle_message(message)

    def _handle_message(self, message: dict[str, Any]) -> None:
        kind = str(message.get("type", "unknown"))

        if kind == "chat":
            self._append_event(
                kind="chat",
                text=str(message.get("message", "")),
                sender=str(message.get("from", "unknown")),
                scope="room",
            )
            return

        if kind == "private":
            self._append_event(
                kind="chat",
                text=str(message.get("message", "")),
                sender=str(message.get("from", "unknown")),
                scope="private",
            )
            return

        if kind == "system":
            self._append_event(kind="system", text=str(message.get("message", "")))
            return

        if kind == "error":
            self._append_event(kind="error", text=str(message.get("message", "")))
            return

        if kind == "roster":
            users = [str(user) for user in message.get("users", [])]
            with self._lock:
                self._users = users
            return

        self._append_event(kind="system", text=str(message))

    def _append_event(self, kind: str, text: str, sender: str | None = None, scope: str = "room") -> None:
        with self._lock:
            self._append_event_locked(kind=kind, text=text, sender=sender, scope=scope)

    def _append_event_locked(self, kind: str, text: str, sender: str | None = None, scope: str = "room") -> None:
        event = {
            "id": self._next_event_id,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "kind": kind,
            "text": text,
            "sender": sender,
            "scope": scope,
        }
        self._next_event_id += 1
        self._events.append(event)

        if len(self._events) > 700:
            self._events = self._events[-500:]

    def _finalize_disconnect(self, reason: str) -> None:
        with self._lock:
            if not self._connected and self._socket is None and self._socket_file is None:
                return

            sock = self._socket
            sock_file = self._socket_file
            self._socket = None
            self._socket_file = None
            self._running = False
            self._connected = False
            self._users = []
            self._append_event_locked(kind="system", text=reason)

        if sock_file is not None:
            try:
                sock_file.close()
            except OSError:
                pass

        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def create_app(default_server_host: str, default_server_port: int) -> Flask:
    app = Flask(__name__, static_folder=None)
    session = ChatSession()

    @app.get("/")
    def index() -> Any:
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/app.css")
    def css() -> Any:
        return send_from_directory(WEB_DIR, "app.css")

    @app.get("/app.js")
    def js() -> Any:
        return send_from_directory(WEB_DIR, "app.js")

    @app.get("/api/state")
    def state() -> Any:
        snapshot = session.snapshot()
        snapshot["defaultHost"] = default_server_host
        snapshot["defaultPort"] = default_server_port
        return jsonify(snapshot)

    @app.get("/api/events")
    def events() -> Any:
        try:
            after = int(request.args.get("after", "0"))
        except ValueError:
            after = 0
        return jsonify(session.snapshot(after_event_id=after))

    @app.post("/api/connect")
    def connect() -> Any:
        payload = request.get_json(silent=True) or {}
        host = str(payload.get("host", default_server_host))
        username = str(payload.get("username", ""))
        try:
            port = int(payload.get("port", default_server_port))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Port must be a valid number."}), 400

        ok, error = session.connect(host=host, port=port, username=username)
        if not ok:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True})

    @app.post("/api/disconnect")
    def disconnect() -> Any:
        session.disconnect()
        return jsonify({"ok": True})

    @app.post("/api/send")
    def send_message() -> Any:
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", ""))
        recipient = str(payload.get("recipient", "Everyone"))
        ok, error = session.send_user_input(text=text, recipient=recipient)
        if not ok:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True})

    @app.post("/api/roster")
    def request_roster() -> Any:
        ok, error = session.send({"type": "list"})
        if not ok:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True})

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CMPT 371 browser-based chat client.")
    parser.add_argument(
        "--server-host",
        default=DEFAULT_SERVER_HOST,
        help=f"Default chat server host for the web UI (default: {DEFAULT_SERVER_HOST})",
    )
    parser.add_argument(
        "--server-port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=f"Default chat server port for the web UI (default: {DEFAULT_SERVER_PORT})",
    )
    parser.add_argument(
        "--web-host",
        default=DEFAULT_WEB_HOST,
        help=f"Host for the local web UI (default: {DEFAULT_WEB_HOST})",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=DEFAULT_WEB_PORT,
        help=f"Port for the local web UI (default: {DEFAULT_WEB_PORT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app(default_server_host=args.server_host, default_server_port=args.server_port)
    print(f"Web client running at http://{args.web_host}:{args.web_port}")

    try:
        from waitress import serve
    except ImportError:
        print("Waitress is not installed; falling back to Flask's development server.")
        app.run(host=args.web_host, port=args.web_port, debug=False, use_reloader=False)
        return

    serve(app, host=args.web_host, port=args.web_port, threads=8)


if __name__ == "__main__":
    main()
