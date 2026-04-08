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
from dataclasses import dataclass

from common import safe_json_loads, send_json


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5050


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

    def start(self) -> None:
        """Start the TCP server and accept clients forever."""

        self._running = True
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
            self._broadcast_chat(sender, text)
            return

        if message_type == "private":
            target = str(message.get("target", "")).strip()
            text = str(message.get("text", "")).strip()
            if not target or not text:
                self._send_error(sender, "Private messages require a target username and text.")
                return
            self._send_private(sender, target, text)
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

    def _send_private(self, sender: str, target: str, text: str) -> None:
        with self._lock:
            recipient = self._clients.get(target)

        if recipient is None:
            self._send_error(sender, f"User '{target}' is not online.")
            return

        self._send_to_user(target, {"type": "private", "from": sender, "message": text})
        if target != sender:
            self._send_to_user(sender, {"type": "system", "message": f"Private message sent to {target}."})

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
            self._broadcast_system(f"{username} left the room.")
            self._broadcast_roster()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CMPT 371 TCP chat server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind to (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind to (default: {DEFAULT_PORT})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ChatServer(args.host, args.port)
    server.start()


if __name__ == "__main__":
    main()
