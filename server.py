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
            --bg: #0b1324;
            --panel: #101a33;
            --panel-soft: #162447;
            --surface: #0f1b38;
            --text: #e6edf8;
            --muted: #9cafcc;
            --accent: #55c7ff;
            --accent-2: #57f2d3;
            --warn: #ffd166;
            --error: #ff7b8a;
            --ok: #73f0b5;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: "Avenir Next", "Futura", "Trebuchet MS", sans-serif;
        }
        body {
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .background-layer {
            position: fixed;
            inset: 0;
            background:
                radial-gradient(circle at 15% 20%, rgba(87, 242, 211, 0.2), transparent 30%),
                radial-gradient(circle at 80% 10%, rgba(85, 199, 255, 0.2), transparent 35%),
                radial-gradient(circle at 70% 70%, rgba(255, 122, 138, 0.12), transparent 30%),
                linear-gradient(135deg, #0a1020 0%, #0b1324 45%, #0d1a32 100%);
            z-index: 0;
        }

        main {
            position: relative;
            z-index: 1;
            max-width: 1400px;
            margin: 0 auto;
            padding: 22px;
        }

        .topbar {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 20px;
            margin-bottom: 18px;
        }

        h1 {
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 6px;
            letter-spacing: 0.3px;
        }

        .subtitle {
            color: var(--muted);
            margin: 0;
        }

        .status-panel {
            text-align: right;
        }

        .status-chip {
            display: inline-block;
            padding: 8px 14px;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            font-weight: 700;
            margin-bottom: 8px;
        }

        .status-chip.offline {
            background: rgba(255, 123, 138, 0.16);
            color: #ffd2d8;
        }

        .status-chip.connecting {
            background: rgba(255, 209, 102, 0.16);
            color: #ffe8a8;
        }

        .status-chip.online {
            background: rgba(115, 240, 181, 0.14);
            color: #cbffe8;
        }

        #hintText {
            margin: 0;
            color: var(--muted);
            line-height: 1.4;
            max-width: 480px;
        }

        .cards {
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
            gap: 16px;
        }

        .card {
            border-radius: 22px;
            background: linear-gradient(165deg, rgba(16, 26, 51, 0.95), rgba(11, 19, 36, 0.95));
            border: 1px solid rgba(125, 174, 255, 0.18);
            box-shadow: 0 18px 50px rgba(4, 10, 22, 0.45);
            padding: 16px;
        }

        .span-4 {
            grid-column: span 4;
        }

        .span-6 {
            grid-column: span 6;
        }

        .span-8 {
            grid-column: span 8;
        }

        .span-12 {
            grid-column: span 12;
        }

        .card h2 {
            font-size: 1rem;
            margin-bottom: 10px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .metrics {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
        }

        .metric-box {
            background: linear-gradient(170deg, rgba(22, 36, 71, 0.9), rgba(17, 30, 59, 0.9));
            border: 1px solid rgba(120, 163, 240, 0.16);
            border-radius: 14px;
            padding: 10px;
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.83rem;
            margin-bottom: 6px;
        }

        .metric {
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--accent);
            line-height: 1.1;
            font-variant-numeric: tabular-nums;
        }

        .metric.ok {
            color: var(--ok);
        }

        .metric.warn {
            color: var(--warn);
        }

        .metric.error {
            color: var(--error);
        }

        ul {
            list-style: none;
            margin-top: 6px;
            max-height: 260px;
            overflow: auto;
            border-radius: 12px;
            border: 1px solid rgba(125, 174, 255, 0.2);
            background: rgba(7, 15, 29, 0.7);
        }

        li {
            padding: 10px 12px;
            border-bottom: 1px solid rgba(146, 194, 255, 0.1);
            font-size: 0.92rem;
        }

        li:last-child {
            border-bottom: 0;
        }

        li.empty {
            color: var(--muted);
            font-style: italic;
        }

        .row {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 8px;
            color: var(--muted);
            font-size: 0.93rem;
        }

        .session-row {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: center;
        }

        .session-name {
            font-weight: 700;
            color: var(--text);
        }

        .session-addr {
            font-size: 0.82rem;
            color: var(--muted);
            font-variant-numeric: tabular-nums;
        }

        .event-time {
            color: var(--muted);
            margin-right: 8px;
            font-variant-numeric: tabular-nums;
        }

        .event-kind {
            font-weight: 700;
            margin-right: 8px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .kind-system {
            color: var(--accent);
        }

        .kind-chat {
            color: var(--ok);
        }

        .kind-private {
            color: #d9b3ff;
        }

        .kind-join,
        .kind-leave {
            color: var(--warn);
        }

        .kind-error {
            color: var(--error);
        }

        .event-text {
            color: var(--text);
        }

        .endpoint {
            font-family: "SFMono-Regular", Menlo, Consolas, monospace;
            font-weight: 600;
            color: #d3e8ff;
        }

        @media (max-width: 1050px) {
            .span-4,
            .span-6,
            .span-8 {
                grid-column: span 12;
            }

            .status-panel {
                text-align: left;
            }

            .topbar {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="background-layer"></div>
    <main>
        <header class="topbar">
            <div>
                <h1>FluxChat Server Dashboard</h1>
                <p class="subtitle">Live operational monitoring for the TCP chat server.</p>
            </div>
            <div class="status-panel">
                <span id="statusChip" class="status-chip connecting">Loading...</span>
                <p id="hintText">Waiting for dashboard metrics...</p>
            </div>
        </header>

        <div class="cards">
            <section class="card span-8">
                <h2>Live Metrics</h2>
                <div class="metrics">
                    <div class="metric-box">
                        <div class="metric-label">Active users</div>
                        <div class="metric ok" id="activeUserCount">0</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Total connections</div>
                        <div class="metric" id="totalConnections">0</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Total messages</div>
                        <div class="metric" id="totalMessages">0</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Uptime</div>
                        <div class="metric" id="uptime">0s</div>
                    </div>
                </div>
                <div class="row" style="margin-top: 12px;"><span>Active usernames</span><span id="activeUsersLabel">none</span></div>
            </section>

            <section class="card span-4">
                <h2>Traffic</h2>
                <div class="row"><span>Public messages</span><span id="publicMessages">0</span></div>
                <div class="row"><span>Private messages</span><span id="privateMessages">0</span></div>
                <div class="row"><span>Messages/min</span><span id="messageRate">0.00</span></div>
                <div class="row"><span>Disconnect events</span><span id="disconnectCount">0</span></div>
                <div class="row"><span>Error events</span><span id="errorCount">0</span></div>
            </section>

            <section class="card span-4">
                <h2>Endpoints</h2>
                <div class="row"><span>Socket server</span><span class="endpoint" id="serverEndpoint">-</span></div>
                <div class="row"><span>Dashboard</span><span class="endpoint" id="dashboardEndpoint">-</span></div>
                <div class="row"><span>Last updated</span><span id="lastUpdated">-</span></div>
            </section>

            <section class="card span-8">
                <h2>Active Sessions</h2>
                <ul id="sessions"></ul>
            </section>

            <section class="card span-12">
                <h2>Recent Events</h2>
                <ul id="events"></ul>
            </section>
        </div>
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

        function escapeHtml(value) {
            var text = String(value === undefined || value === null ? "" : value);
            return text.replace(/[&<>"']/g, function (char) {
                if (char === "&") return "&amp;";
                if (char === "<") return "&lt;";
                if (char === ">") return "&gt;";
                if (char === '"') return "&quot;";
                return "&#39;";
            });
        }

        function setText(id, value) {
            var element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        }

        function renderSessions(sessions) {
            var sessionsEl = document.getElementById("sessions");
            if (!Array.isArray(sessions) || sessions.length === 0) {
                sessionsEl.innerHTML = "<li class='empty'>No users connected</li>";
                return;
            }

            sessionsEl.innerHTML = sessions.map(function (item) {
                var name = escapeHtml(item.username || "unknown");
                var addr = escapeHtml(item.address || "-");
                return "<li><div class='session-row'><span class='session-name'>" + name + "</span><span class='session-addr'>" + addr + "</span></div></li>";
            }).join("");
        }

        function renderEvents(events) {
            var eventsEl = document.getElementById("events");
            if (!Array.isArray(events) || events.length === 0) {
                eventsEl.innerHTML = "<li class='empty'>No events yet</li>";
                return;
            }

            eventsEl.innerHTML = events.map(function (item) {
                var timestamp = escapeHtml(item.timestamp || "");
                var rawKind = String(item.kind || "info").toLowerCase();
                var kind = escapeHtml(rawKind.toUpperCase());
                var text = escapeHtml(item.text || "");
                var kindClass = "kind-" + rawKind.replace(/[^a-z0-9_-]/g, "");
                return "<li><span class='event-time'>" + timestamp + "</span><span class='event-kind " + kindClass + "'>" + kind + "</span><span class='event-text'>" + text + "</span></li>";
            }).join("");
        }

        function setStatus(isOnline, message) {
            var chip = document.getElementById("statusChip");
            var hint = document.getElementById("hintText");
            if (!chip || !hint) {
                return;
            }

            if (isOnline) {
                chip.className = "status-chip online";
                chip.textContent = "Live";
                hint.textContent = message;
            } else {
                chip.className = "status-chip offline";
                chip.textContent = "Offline";
                hint.textContent = message;
            }
        }

        async function refreshDashboard() {
            try {
                var response = await fetch("/api/status?ts=" + Date.now(), { cache: "no-store" });
                if (!response.ok) {
                    throw new Error("status request failed");
                }

                var data = await response.json();
                setText("activeUserCount", data.activeUserCount || 0);
                setText("activeUsersLabel", (Array.isArray(data.activeUsers) && data.activeUsers.length > 0) ? data.activeUsers.join(", ") : "none");
                setText("totalConnections", data.totalConnections || 0);
                setText("publicMessages", data.publicMessages || 0);
                setText("privateMessages", data.privateMessages || 0);
                setText("totalMessages", data.totalMessages || 0);
                setText("disconnectCount", data.disconnectCount || 0);
                setText("errorCount", data.errorCount || 0);
                setText("messageRate", Number(data.messagesPerMinute || 0).toFixed(2));
                setText("uptime", formatUptime(data.uptimeSeconds || 0));
                setText("serverEndpoint", String(data.serverHost || "-") + ":" + String(data.serverPort || "-"));
                if (data.dashboardHost && data.dashboardPort) {
                    setText("dashboardEndpoint", String(data.dashboardHost) + ":" + String(data.dashboardPort));
                } else {
                    setText("dashboardEndpoint", "disabled");
                }
                setText("lastUpdated", new Date().toLocaleTimeString());

                renderSessions(data.activeSessions || []);
                renderEvents(data.recentEvents || []);
                setStatus(true, "Live updates every 1 second. Last refresh " + new Date().toLocaleTimeString() + ".");
            } catch (error) {
                setStatus(false, "Dashboard temporarily unavailable. Check server process and refresh.");
            }
        }

        window.addEventListener("load", function () {
            refreshDashboard();
            setInterval(refreshDashboard, 1000);
        });
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
        self._disconnect_count = 0
        self._error_count = 0
        self._public_messages = 0
        self._private_messages = 0
        self._recent_events: list[dict[str, str]] = []
        self._dashboard_host = ""
        self._dashboard_port = 0

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
        with self._lock:
            self._error_count += 1
            self._record_event_locked("error", f"Error for {username}: {text}")
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
            with self._lock:
                self._disconnect_count += 1
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
            active_sessions = [
                {
                    "username": session.username,
                    "address": f"{session.address[0]}:{session.address[1]}",
                }
                for session in sorted(self._clients.values(), key=lambda item: item.username.lower())
            ]
            uptime_seconds = int(max(0.0, time.time() - self._started_at))
            total_messages = self._public_messages + self._private_messages
            if uptime_seconds > 0:
                messages_per_minute = round(total_messages / (uptime_seconds / 60.0), 2)
            else:
                messages_per_minute = 0.0

            return {
                "running": self._running,
                "serverHost": self.host,
                "serverPort": self.port,
                "dashboardHost": self._dashboard_host,
                "dashboardPort": self._dashboard_port,
                "activeUsers": active_users,
                "activeSessions": active_sessions,
                "activeUserCount": len(active_users),
                "totalConnections": self._total_connections,
                "disconnectCount": self._disconnect_count,
                "errorCount": self._error_count,
                "publicMessages": self._public_messages,
                "privateMessages": self._private_messages,
                "totalMessages": total_messages,
                "messagesPerMinute": messages_per_minute,
                "uptimeSeconds": uptime_seconds,
                "startedAt": datetime.fromtimestamp(self._started_at).strftime("%Y-%m-%d %H:%M:%S"),
                "recentEvents": list(self._recent_events),
            }

    def start_dashboard(self, host: str, port: int) -> None:
        """Start an optional web dashboard in a daemon thread."""

        try:
            from flask import Flask, jsonify
        except ImportError:
            print("Dashboard disabled: Flask is not available in this environment.")
            return

        with self._lock:
            self._dashboard_host = host
            self._dashboard_port = port

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
