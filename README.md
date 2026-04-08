# CMPT371 Assignment 3 - FluxChat

**Course:** CMPT 371 - Data Communications and Networking  
**Architecture:** TCP client-server chat application with a browser GUI

## Group Members

| Name | Student ID | Email |
| --- | --- | --- |
| Navjot Singh | 301609090 | nsn8@sfu.ca |
| Dilpreet Singh Mann | 301608343 | dsm19@sfu.ca |
| Karnpreet Cheema | 301582425 | ksc30@sfu.ca |

Group-size note: this team has an approved exception to submit as a group of 3.

## 1. Project Overview and Description

FluxChat is a TCP multi-client chat room written in Python using socket programming.
A central server accepts concurrent clients, handles username registration, routes public and private messages, and keeps an online-user roster.

The client is a browser-based GUI served by Flask. It provides a responsive chat interface with a connection panel, roster, conversation feed, and command-aware message composer.

## 2. System Limitations and Edge Cases

- **Concurrent clients:** The server uses threads for each connected client. This supports multiple users, but thread count is still limited by machine resources.
- **In-memory state only:** Restarting the server clears users and chat activity.
- **No persistence layer:** Message history is not stored in a database or file.
- **No transport encryption:** Traffic is plain TCP for assignment scope (no TLS).
- **Single active session per client process:** Each `client.py` instance manages one active socket connection.
- **Username uniqueness:** Duplicate usernames are rejected while already connected.

## 3. Video Demo (Maximum 2 Minutes)

- Video demo link (replace placeholder before submission): https://<add-video-link-here>
- Keep the video at or below 120 seconds.
- Demonstrate: connection setup, data exchange (public + private), and clean termination.

## 4. Prerequisites (Fresh Environment)

- Python 3.10 or newer
- `pip` for dependency installation
- Dependencies listed in `requirements.txt`:
  - Flask
  - Waitress

## 5. Setup

From a fresh environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6. Step-by-Step Run Guide

### Step 1: Start the server

```bash
python3 server.py --host 0.0.0.0 --port 5050
```

Optional server dashboard (safe to skip):

```bash
python3 server.py --host 0.0.0.0 --port 5050 --dashboard --dashboard-host 127.0.0.1 --dashboard-port 5051
```

If dashboard mode is used, open:

```text
http://127.0.0.1:5051
```

Expected output includes:

```text
Chat server listening on 0.0.0.0:5050
Waiting for clients...
```

### Step 2: Start browser client instance 1

In a new terminal:

```bash
python3 client.py --server-host 127.0.0.1 --server-port 5050 --web-host 127.0.0.1 --web-port 8000
```

Open:

```text
http://127.0.0.1:8000
```

### Step 3: Start browser client instance 2

In another terminal:

```bash
python3 client.py --server-host 127.0.0.1 --server-port 5050 --web-host 127.0.0.1 --web-port 8001
```

Open:

```text
http://127.0.0.1:8001
```

### Step 4: Connect, exchange messages, and disconnect

In each browser tab:

1. Enter host, port, and a unique username.
2. Send at least one public message.
3. Send at least one private message using recipient selection.
4. Disconnect cleanly.

## 7. GUI Controls and Command Reference

- Select `Everyone` to send a public room message.
- Select a username in the roster to send a private message.
- Press Enter in the message box to send quickly.
- Use **Help** for command reminders.
- Use **Request roster** to refresh online users.
- Use **Clear chat** to reset the visible conversation panel.
- Command support: `/help`, `/list`, `/msg <user> <text>`, `/quit`.

## 8. Technical Protocol Summary (JSON over TCP)

Application messages use newline-delimited JSON over TCP.

- **Join:** `{"type":"join","username":"alice"}`
- **Public chat:** `{"type":"chat","text":"hello room"}`
- **Private chat:** `{"type":"private","target":"bob","text":"hi"}`
- **Roster request:** `{"type":"list"}`
- **Quit:** `{"type":"quit"}`

Server responses include message types such as `system`, `chat`, `private`, `roster`, and `error`.

## 9. Academic Integrity and References

### Code origin

- Core socket protocol, multi-client server behavior, and message routing were implemented by the team.
- Frontend interaction is served through a Flask-based web client included in this repository.

### GenAI usage disclosure

- GitHub Copilot was used for limited assistance with frontend UI design ideas and for improving selected code comments to increase readability during debugging.

### References

- Python Socket Programming HOWTO: https://docs.python.org/3/howto/sockets.html
- Python `socket` library docs: https://docs.python.org/3/library/socket.html
- Flask documentation: https://flask.palletsprojects.com/
- Waitress documentation: https://docs.pylonsproject.org/projects/waitress/en/stable/

