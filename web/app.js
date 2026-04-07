const state = {
  connected: false,
  lastEventId: 0,
  users: [],
};

const els = {
  hostInput: document.getElementById("hostInput"),
  portInput: document.getElementById("portInput"),
  usernameInput: document.getElementById("usernameInput"),
  connectBtn: document.getElementById("connectBtn"),
  disconnectBtn: document.getElementById("disconnectBtn"),
  statusChip: document.getElementById("statusChip"),
  hintText: document.getElementById("hintText"),
  userList: document.getElementById("userList"),
  chatFeed: document.getElementById("chatFeed"),
  recipientSelect: document.getElementById("recipientSelect"),
  messageInput: document.getElementById("messageInput"),
  sendBtn: document.getElementById("sendBtn"),
  helpBtn: document.getElementById("helpBtn"),
  rosterBtn: document.getElementById("rosterBtn"),
  clearBtn: document.getElementById("clearBtn"),
  toast: document.getElementById("toast"),
};

let pollTimer = null;
let toastTimer = null;

function showToast(text, isError = false) {
  els.toast.textContent = text;
  els.toast.style.borderColor = isError ? "rgba(255, 123, 138, 0.42)" : "rgba(125, 174, 255, 0.32)";
  els.toast.classList.remove("hidden");
  if (toastTimer) {
    window.clearTimeout(toastTimer);
  }
  toastTimer = window.setTimeout(() => {
    els.toast.classList.add("hidden");
  }, 2400);
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setConnectionUi(connected) {
  state.connected = connected;
  els.connectBtn.disabled = connected;
  els.disconnectBtn.disabled = !connected;
  els.hostInput.disabled = connected;
  els.portInput.disabled = connected;
  els.usernameInput.disabled = connected;
  els.recipientSelect.disabled = !connected;
  els.sendBtn.disabled = !connected;
  els.messageInput.disabled = !connected;
}

function setStatus(kind, hint) {
  els.statusChip.classList.remove("offline", "connecting", "online");
  if (kind === "connecting") {
    els.statusChip.classList.add("connecting");
    els.statusChip.textContent = "Connecting";
  } else if (kind === "online") {
    els.statusChip.classList.add("online");
    els.statusChip.textContent = "Online";
  } else {
    els.statusChip.classList.add("offline");
    els.statusChip.textContent = "Offline";
  }
  if (hint) {
    els.hintText.textContent = hint;
  }
}

function updateUsers(users) {
  state.users = users;
  const currentRecipient = els.recipientSelect.value || "Everyone";

  els.userList.innerHTML = "";
  for (const user of users) {
    const li = document.createElement("li");
    li.textContent = user;
    li.addEventListener("click", () => {
      els.recipientSelect.value = user;
      updateSendLabel();
      highlightSelectedUser();
      els.messageInput.focus();
    });
    els.userList.appendChild(li);
  }

  els.recipientSelect.innerHTML = "";
  const everyoneOption = document.createElement("option");
  everyoneOption.textContent = "Everyone";
  els.recipientSelect.appendChild(everyoneOption);

  for (const user of users) {
    const option = document.createElement("option");
    option.textContent = user;
    els.recipientSelect.appendChild(option);
  }

  if (users.includes(currentRecipient) || currentRecipient === "Everyone") {
    els.recipientSelect.value = currentRecipient;
  } else {
    els.recipientSelect.value = "Everyone";
  }

  highlightSelectedUser();
  updateSendLabel();
}

function highlightSelectedUser() {
  const selected = els.recipientSelect.value;
  for (const li of els.userList.children) {
    li.classList.toggle("selected", li.textContent === selected);
  }
}

function updateSendLabel() {
  const selected = els.recipientSelect.value;
  els.sendBtn.textContent = selected && selected !== "Everyone" ? `Private to ${selected}` : "Send to room";
}

function renderEvent(event) {
  const message = document.createElement("div");
  message.className = `message ${event.kind} ${event.scope || "room"}`;

  const time = document.createElement("span");
  time.className = "time";
  time.textContent = `[${event.timestamp}]`;

  const meta = document.createElement("span");
  meta.className = "meta";

  if (event.kind === "chat") {
    const label = event.scope === "private" ? "Private" : "Room";
    meta.textContent = `${label} ${event.sender || "unknown"}`;
  } else if (event.kind === "error") {
    meta.textContent = "Error";
  } else {
    meta.textContent = "System";
  }

  const text = document.createElement("div");
  text.className = "text";
  text.innerHTML = escapeHtml(event.text || "");

  message.appendChild(time);
  message.appendChild(meta);
  message.appendChild(text);
  return message;
}

function appendEvents(events) {
  if (!Array.isArray(events) || events.length === 0) {
    return;
  }

  const shouldAutoScroll =
    els.chatFeed.scrollTop + els.chatFeed.clientHeight >= els.chatFeed.scrollHeight - 90;

  for (const event of events) {
    els.chatFeed.appendChild(renderEvent(event));
    state.lastEventId = Math.max(state.lastEventId, event.id || 0);
  }

  if (shouldAutoScroll) {
    els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
  }
}

async function apiGet(path) {
  const response = await fetch(path, { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function apiPost(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function refreshState() {
  const data = await apiGet("/api/state");

  if (!els.hostInput.value) {
    els.hostInput.value = data.defaultHost || "127.0.0.1";
  }
  if (!els.portInput.value) {
    els.portInput.value = data.defaultPort || 5050;
  }

  setConnectionUi(Boolean(data.connected));
  setStatus(data.connected ? "online" : "offline", data.connected
    ? `Connected to ${data.host}:${data.port}`
    : "Connect to the server to start chatting.");

  if (data.username && !els.usernameInput.value) {
    els.usernameInput.value = data.username;
  }

  updateUsers(data.users || []);
  appendEvents(data.events || []);
}

async function pollEvents() {
  try {
    const data = await apiGet(`/api/events?after=${state.lastEventId}`);
    setConnectionUi(Boolean(data.connected));

    if (data.connected) {
      setStatus("online", `Connected to ${data.host}:${data.port}`);
    } else {
      setStatus("offline", "Connect to the server to start chatting.");
    }

    updateUsers(data.users || []);
    appendEvents(data.events || []);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function connect() {
  const host = els.hostInput.value.trim();
  const port = Number(els.portInput.value);
  const username = els.usernameInput.value.trim();

  if (!host || !port || !username) {
    showToast("Host, port, and username are required.", true);
    return;
  }

  setStatus("connecting", `Connecting to ${host}:${port}...`);
  try {
    await apiPost("/api/connect", { host, port, username });
    showToast("Connected successfully.");
    await refreshState();
  } catch (error) {
    setStatus("offline", "Connect to the server to start chatting.");
    showToast(error.message, true);
  }
}

async function disconnect() {
  try {
    await apiPost("/api/disconnect");
    showToast("Disconnected.");
    await refreshState();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function sendMessage() {
  const text = els.messageInput.value.trim();
  const recipient = els.recipientSelect.value || "Everyone";

  if (!text) {
    return;
  }

  els.messageInput.value = "";
  try {
    await apiPost("/api/send", { text, recipient });
    await pollEvents();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function requestRoster() {
  try {
    await apiPost("/api/roster");
    await pollEvents();
  } catch (error) {
    showToast(error.message, true);
  }
}

function showHelp() {
  showToast("Commands: /help, /list, /msg <user> <text>, /quit");
}

function clearChat() {
  els.chatFeed.innerHTML = "";
}

function wireEvents() {
  els.connectBtn.addEventListener("click", connect);
  els.disconnectBtn.addEventListener("click", disconnect);
  els.sendBtn.addEventListener("click", sendMessage);
  els.rosterBtn.addEventListener("click", requestRoster);
  els.helpBtn.addEventListener("click", showHelp);
  els.clearBtn.addEventListener("click", clearChat);
  els.recipientSelect.addEventListener("change", () => {
    updateSendLabel();
    highlightSelectedUser();
  });

  els.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      sendMessage();
    }
  });
}

async function bootstrap() {
  wireEvents();
  await refreshState();
  updateSendLabel();

  if (pollTimer) {
    window.clearInterval(pollTimer);
  }
  pollTimer = window.setInterval(pollEvents, 700);
}

bootstrap().catch((error) => {
  showToast(error.message, true);
});
