# CMPT371 Assignment 3 - FluxChat

## Project Overview

This project is a TCP multi-client chat room written in Python. A central server accepts several clients at the same time, assigns usernames, broadcasts public messages, supports private messages, and shows the list of connected users.

The client is a polished browser GUI served by Flask. It includes a modern responsive interface with a connection panel, roster, live conversation feed, and command-aware message composer.

## Team Information

| Member | Name | Student ID | Email |
| --- | --- | --- | --- |
| 1 | Navjot Singh | 301609090 | nsn8@sfu.ca |
| 2 | Dilpreet Singh Mann | 301608343 | dsm19@sfu.ca |
| 3 | Karnpreet Cheema | 301582425 | ksc30@sfu.ca |

## Features

- TCP client-server architecture
- Multiple concurrent clients
- Username registration
- Public broadcast chat
- Private messaging with `/msg`
- Online user list with `/list`
- Graceful disconnect handling with `/quit`
- Modern responsive browser GUI with connection panel, roster, chat feed, and message composer

## Limitations

- The server keeps all state in memory, so restarting it clears the chat room.
- Messages are not stored permanently.
- The browser client keeps one active chat session per running `client.py` process.
- A username can only be used by one connected client at a time.
- The system does not encrypt traffic.

## Requirements

- Python 3.10 or newer
- Flask and Waitress (installed through `requirements.txt`)

## Setup

From a fresh environment:

1. Install Python 3.
2. Open a terminal in the project folder.
3. Optional but recommended: create a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

4. Install dependencies.

```bash
pip install -r requirements.txt
```

## Run the Server

```bash
python3 server.py --host 0.0.0.0 --port 5050
```

## Run the GUI Client

Open a second terminal and launch the local web client:

```bash
python3 client.py --server-host 127.0.0.1 --server-port 5050 --web-host 127.0.0.1 --web-port 8000
```

For a second browser client instance:

```bash
python3 client.py --server-host 127.0.0.1 --server-port 5050 --web-host 127.0.0.1 --web-port 8001
```

Then open:

```text
http://127.0.0.1:8000
```

For the second instance:

```text
http://127.0.0.1:8001
```

In the page, enter host, port, and username, then click Connect.

The client starts with Waitress (production WSGI server) if available.

## GUI Controls

- Select `Everyone` to broadcast to the room.
- Select a user from the roster to send a private message.
- Press Enter in the message box to send.
- Use the Help button for command reminders.
- Use Request roster to refresh the online user list.
- Use Clear chat to reset the visible conversation.
- Use `/help`, `/list`, `/msg <user> <text>`, and `/quit` if you want to type commands directly.

## Notes on Readability

The code is split into small files with shared protocol helpers to keep the server and client logic easy to follow.
