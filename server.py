"""TCP chat server for CMPT 371 Assignment 3.

Features:
- multiple concurrent clients
- username registration
- public broadcast messages
- private messages via /msg
- client list via /list
- graceful disconnect handling
"""

from __future__ import annotations

import argparse
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from common import safe_json_loads, send_json


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5050
DEFAULT_DASHBOARD_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 5051

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>FluxChat Server Dashboard</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f5f7fb;
            --panel: #ffffff;
            --text: #13213a;
            --muted: #55637e;
            --accent: #1e88e5;
            --good: #157347;
            --shadow: 0 12px 28px rgba(12, 28, 62, 0.08);
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        }
        body {
            background: linear-gradient(180deg, #f4f9ff 0%, #eef3fb 100%);
            color: var(--text);
            min-height: 100vh;
            padding: 18px;
        }
        main {
            max-width: 1050px;
            margin: 0 auto;
        }
        h1 {
            font-size: clamp(1.4rem, 2.4vw, 2rem);
            margin-bottom: 8px;
        }
        .subtitle {
            color: var(--muted);
            margin-bottom: 14px;
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 12px;
            margin-bottom: 12px;
        }
        .card {
            background: var(--panel);
            border-radius: 14px;
            box-shadow: var(--shadow);
            padding: 14px;
            border: 1px solid #e3ebf7;
        }
        .card h2 {
            font-size: 0.95rem;
            margin-bottom: 10px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .metric {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent);
            line-height: 1.1;
            margin-bottom: 8px;
        }
        ul {
            list-style: none;
            margin-top: 6px;
            max-height: 210px;
            overflow: auto;
            border-radius: 8px;
            border: 1px solid #ebf0f8;
        }
        li {
            padding: 8px 10px;
            border-bottom: 1px solid #edf2fa;
            font-size: 0.92rem;
        }
        li:last-child {
            border-bottom: 0;
        }
        .row {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 4px;
            color: var(--muted);
            font-size: 0.93rem;
        }
        .event-time {
            color: #4e648b;
            margin-right: 8px;
            font-variant-numeric: tabular-nums;
        }
        .event-kind {
            color: var(--good);
            font-weight: 600;
            margin-right: 8px;
        }
        .status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 5px 10px;
            background: #e8f5e9;
            border: 1px solid #c7e7cf;
            border-radius: 999px;
            font-size: 0.86rem;
            color: #1f5a38;
            margin-bottom: 12px;
        }
        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #2e7d32;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.4); opacity: 0.45; }
        }
    </style>
</head>
<body>
    <main>
        <h1>FluxChat Server Dashboard</h1>
        <p class="subtitle">Live operational view for the TCP chat server.</p>
        <div class="status"><span class="dot"></span><span id="statusText">Running</span></div>

        <div class="cards">
            <section class="card">
                <h2>Connections</h2>
                <div class="metric" id="activeUserCount">0</div>
                <div class="row"><span>Active users</span><span id="activeUsersLabel">none</span></div>
                <div class="row"><span>Total connections</span><span id="totalConnections">0</span></div>
            </section>

            <section class="card">
                <h2>Traffic</h2>
                <div class="row"><span>Public messages</span><span id="publicMessages">0</span></div>
                <div class="row"><span>Private messages</span><span id="privateMessages">0</span></div>
                <div class="row"><span>Uptime</span><span id="uptime">0s</span></div>
            </section>

            <section class="card">
                <h2>Socket Server</h2>
                <div class="row"><span>Host</span><span id="serverHost">-</span></div>
                <div class="row"><span>Port</span><span id="serverPort">-</span></div>
                <h2 style="margin-top: 12px;">Online Users</h2>
                <ul id="users"></ul>
            </section>
        </div>

        <section class="card">
            <h2>Recent Events</h2>
            <ul id="events"></ul>
        </section>
    </main>

    <script>
        function formatUptime(totalSeconds) {
            var sec = Math.max(0, Number(totalSeconds) || 0);
            var h = Math.floor(sec / 3600);
            var m = Math.floor((sec % 3600) / 60);
            var s = sec % 60;
            if (h > 0) {
                return h + "h " + m + "m " + s + "s";
            }
            if (m > 0) {
                return m + "m " + s + "s";
            }
            return s + "s";
        }

        function escapeHtml(text) {
            return String(text)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#39;");
        }

        function renderUsers(users) {
            var usersEl = document.getElementById("users");
            if (!Array.isArray(users) || users.length === 0) {
                usersEl.innerHTML = "<li>No users connected</li>";
                return;
            }
            usersEl.innerHTML = users.map(function (name) {
                return "<li>" + escapeHtml(name) + "</li>";
            }).join("");
        }

        function renderEvents(events) {
            var eventsEl = document.getElementById("events");
            if (!Array.isArray(events) || events.length === 0) {
                eventsEl.innerHTML = "<li>No events yet</li>";
                return;
            }
            eventsEl.innerHTML = events.map(function (item) {
                var timestamp = escapeHtml(item.timestamp || "");
                var kind = escapeHtml((item.kind || "info").toUpperCase());
                var text = escapeHtml(item.text || "");
                return "<li><span class=\"event-time\">" + timestamp + "</span><span class=\"event-kind\">" + kind + "</span><span>" + text + "</span></li>";
            }).join("");
        }

        async function refreshDashboard() {
            try {
                var response = await fetch("/api/status", { cache: "no-store" });
                if (!response.ok) {
                    throw new Error("status request failed");
                }

                var data = await response.json();
                document.getElementById("activeUserCount").textContent = data.activeUserCount;
                document.getElementById("activeUsersLabel").textContent = data.activeUserCount === 0 ? "none" : data.activeUsers.join(", ");
                document.getElementById("totalConnections").textContent = data.totalConnections;
                document.getElementById("publicMessages").textContent = data.publicMessages;
                document.getElementById("privateMessages").textContent = data.privateMessages;
                document.getElementById("uptime").textContent = formatUptime(data.uptimeSeconds);
                document.getElementById("serverHost").textContent = data.serverHost;
                document.getElementById("serverPort").textContent = data.serverPort;
                renderUsers(data.activeUsers);
                renderEvents(data.recentEvents);
            } catch (error) {
                document.getElementById("statusText").textContent = "Dashboard temporarily unavailable";
            }
        }

        refreshDashboard();
        setInterval(refreshDashboard, 1000);
    </script>
</body>
</html>
"""


@dataclass(slots=True)
class ClientSession:
    username: str
    sock: socket.socket
    address: tuple[str, int]


class ChatServer:
    """Manage connected chat clients and route messages."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._clients: dict[str, ClientSession] = {}
        self._lock = threading.Lock()
        self._running = False
        self._started_at = time.time()
        self._total_connections = 0
        self._public_messages = 0
        self._private_messages = 0
        self._recent_events: list[dict[str, str]] = []

    def start(self) -> None:
        """Start the TCP server and accept clients forever."""

        self._running = True
        self._record_event("system", f"Server listening on {self.host}:{self.port}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self.host, self.port))
            server_sock.listen()

            print(f"Chat server listening on {self.host}:{self.port}")
            print("Waiting for clients...\n")

            while self._running:
                try:
                    client_sock, address = server_sock.accept()
                except OSError:
                    break

                # Handle each client in its own thread so the accept loop stays responsive.
                threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, address),
                    daemon=True,
                ).start()

    def _handle_client(self, client_sock: socket.socket, address: tuple[str, int]) -> None:
        """Register a client and then process all incoming messages."""

        username = ""
        try:
            client_file = client_sock.makefile("r", encoding="utf-8", newline="\n")

            # Require a join packet first so the server can register identity safely.
            join_raw = client_file.readline()
            if not join_raw:
                return

            join_message = safe_json_loads(join_raw)
            if not join_message or join_message.get("type") != "join":
                send_json(client_sock, {"type": "error", "message": "First message must be a join packet."})
                return

            requested_username = str(join_message.get("username", "")).strip()
            if not requested_username:
                send_json(client_sock, {"type": "error", "message": "Username cannot be empty."})
                return

            with self._lock:
                if requested_username in self._clients:
                    send_json(client_sock, {"type": "error", "message": f"Username '{requested_username}' is already in use."})
                    return

                username = requested_username
                self._clients[username] = ClientSession(username=username, sock=client_sock, address=address)
                self._total_connections += 1
                self._record_event_locked("join", f"{username} connected from {address[0]}:{address[1]}")

            send_json(client_sock, {"type": "system", "message": f"Welcome, {username}! Type /help for commands."})
            self._broadcast_system(f"{username} joined the room.", exclude=username)
            self._broadcast_roster()

            for raw_line in client_file:
                message = safe_json_loads(raw_line)
                if not message:
                    send_json(client_sock, {"type": "error", "message": "Invalid JSON message received."})
                    continue

                self._process_message(username, message)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            if username:
                self._remove_client(username)
            try:
                client_sock.close()
            except OSError:
                pass

    def _process_message(self, sender: str, message: dict[str, object]) -> None:
        """Route a message based on its type."""

        message_type = message.get("type")
        if message_type == "chat":
            text = str(message.get("text", "")).strip()
            if not text:
                return
            with self._lock:
                self._public_messages += 1
                self._record_event_locked("chat", f"{sender} (public): {text[:80]}")
            self._broadcast_chat(sender, text)
            return

        if message_type == "private":
            target = str(message.get("target", "")).strip()
            text = str(message.get("text", "")).strip()
            if not target or not text:
                self._send_error(sender, "Private messages require a target username and text.")
                return
            delivered = self._send_private(sender, target, text)
            if delivered:
                with self._lock:
                    self._private_messages += 1
                    self._record_event_locked("private", f"{sender} -> {target}: {text[:80]}")
            return

        if message_type == "list":
            self._send_roster(sender)
            return

        if message_type == "quit":
            self._send_to_user(sender, {"type": "system", "message": "Disconnecting. Goodbye!"})
            self._remove_client(sender)
            return

        self._send_error(sender, f"Unsupported message type: {message_type}")

    def _broadcast_chat(self, sender: str, text: str) -> None:
        self._broadcast({"type": "chat", "from": sender, "message": text})

    def _broadcast_system(self, text: str, exclude: str | None = None) -> None:
        self._broadcast({"type": "system", "message": text}, exclude=exclude)

    def _broadcast_roster(self) -> None:
        with self._lock:
            roster = sorted(self._clients)
        self._broadcast({"type": "roster", "users": roster})

    def _send_roster(self, username: str) -> None:
        with self._lock:
            roster = sorted(self._clients)
        self._send_to_user(username, {"type": "roster", "users": roster})

    def _send_private(self, sender: str, target: str, text: str) -> bool:
        with self._lock:
            recipient = self._clients.get(target)

        if recipient is None:
            self._send_error(sender, f"User '{target}' is not online.")
            return False

        self._send_to_user(target, {"type": "private", "from": sender, "message": text})
        if target != sender:
            self._send_to_user(sender, {"type": "system", "message": f"Private message sent to {target}."})
        return True

    def _send_to_user(self, username: str, payload: dict[str, object]) -> None:
        with self._lock:
            session = self._clients.get(username)

        if session is None:
            return

        try:
            send_json(session.sock, payload)
        except OSError:
            self._remove_client(username)

    def _send_error(self, username: str, text: str) -> None:
        self._record_event("error", f"Error for {username}: {text}")
        self._send_to_user(username, {"type": "error", "message": text})

    def _broadcast(self, payload: dict[str, object], exclude: str | None = None) -> None:
        with self._lock:
            # Copy sessions first to avoid holding the lock during socket writes.
            sessions = list(self._clients.values())

        for session in sessions:
            if exclude is not None and session.username == exclude:
                continue
            try:
                send_json(session.sock, payload)
            except OSError:
                self._remove_client(session.username)

    def _remove_client(self, username: str) -> None:
        """Remove a user from the registry and notify others."""

        removed = False
        with self._lock:
            if username in self._clients:
                session = self._clients.pop(username)
                removed = True
            else:
                session = None

        if session is not None:
            try:
                session.sock.close()
            except OSError:
                pass

        if removed:
            self._record_event("leave", f"{username} disconnected")
            self._broadcast_system(f"{username} left the room.")
            self._broadcast_roster()

    def _record_event(self, kind: str, text: str) -> None:
        with self._lock:
            self._record_event_locked(kind, text)

    def _record_event_locked(self, kind: str, text: str) -> None:
        self._recent_events.append(
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "kind": kind,
                "text": text,
            }
        )
        if len(self._recent_events) > 60:
            self._recent_events = self._recent_events[-40:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            active_users = sorted(self._clients)
            return {
                "serverHost": self.host,
                "serverPort": self.port,
                "activeUsers": active_users,
                "activeUserCount": len(active_users),
                "totalConnections": self._total_connections,
                "publicMessages": self._public_messages,
                "privateMessages": self._private_messages,
                "uptimeSeconds": int(time.time() - self._started_at),
                "recentEvents": list(self._recent_events),
            }

    def start_dashboard(self, host: str, port: int) -> None:
        """Start an optional web dashboard in a daemon thread."""

        try:
            from flask import Flask, jsonify
        except ImportError:
            print("Dashboard disabled: Flask is not available in this environment.")
            return

        app = Flask(__name__, static_folder=None)

        @app.get("/")
        def dashboard_home() -> str:
            return DASHBOARD_HTML

        @app.get("/api/status")
        def dashboard_status() -> Any:
            return jsonify(self.snapshot())

        def run_dashboard() -> None:
            print(f"Server dashboard running at http://{host}:{port}")
            try:
                from waitress import serve
            except ImportError:
                app.run(host=host, port=port, debug=False, use_reloader=False)
                return
            serve(app, host=host, port=port, threads=4)

        threading.Thread(target=run_dashboard, daemon=True).start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CMPT 371 TCP chat server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind to (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind to (default: {DEFAULT_PORT})")
    parser.add_argument("--dashboard", action="store_true", help="Run the optional server web dashboard.")
    parser.add_argument(
        "--dashboard-host",
        default=DEFAULT_DASHBOARD_HOST,
        help=f"Host for dashboard web UI (default: {DEFAULT_DASHBOARD_HOST})",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=DEFAULT_DASHBOARD_PORT,
        help=f"Port for dashboard web UI (default: {DEFAULT_DASHBOARD_PORT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ChatServer(args.host, args.port)
    if args.dashboard:
        server.start_dashboard(host=args.dashboard_host, port=args.dashboard_port)
    server.start()


if __name__ == "__main__":
    main()
