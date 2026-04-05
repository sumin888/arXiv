// ── State ──────────────────────────────────────────────────────────────────
let currentPaper = null;
const conversationHistory = []; // { role: "user"|"assistant", content: string }

// Local FastAPI RAG server — see backend/docs/RAG.md
const API_BASE = "http://127.0.0.1:8000";

// ── DOM refs ───────────────────────────────────────────────────────────────
const paperTitleEl  = document.getElementById("paper-title");
const paperAuthorsEl = document.getElementById("paper-authors");
const statusDot     = document.getElementById("status-dot");
const emptyState    = document.getElementById("empty-state");
const chatContainer = document.getElementById("chat-container");
const messagesEl    = document.getElementById("messages");
const inputArea     = document.getElementById("input-area");
const userInput     = document.getElementById("user-input");
const sendBtn       = document.getElementById("send-btn");

// ── Init: load paper from session storage (in case sidebar opened late) ────
chrome.storage.session.get("currentPaper", ({ currentPaper: stored }) => {
  if (stored) setPaper(stored);
});

// ── Listen for live paper updates from the background worker ───────────────
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "PAPER_UPDATED") {
    setPaper(message.paper);
  }
});

// ── Paper loaded ────────────────────────────────────────────────────────────
function setPaper(paper) {
  currentPaper = paper;
  conversationHistory.length = 0;
  messagesEl.innerHTML = "";

  // Header
  paperTitleEl.textContent = paper.title || paper.arxivId;
  paperAuthorsEl.textContent = paper.authors.slice(0, 3).join(", ") +
    (paper.authors.length > 3 ? ` +${paper.authors.length - 3} more` : "");

  // Show chat UI
  emptyState.hidden = true;
  chatContainer.hidden = false;
  inputArea.hidden = false;

  setStatus("ready");

  // Greeting from the agent
  appendMessage("agent", buildGreeting(paper));
}

function buildGreeting(paper) {
  const authorStr = paper.authors.length
    ? paper.authors.slice(0, 2).join(" and ") + (paper.authors.length > 2 ? " et al." : "")
    : "the authors";
  return `Hi! I'm the AI agent for **${paper.title}** by ${authorStr}.\n\nI'm grounded in the full text of this paper. Ask me anything — methodology, results, related work, or how this connects to other research.`;
}

// ── Send message ────────────────────────────────────────────────────────────
sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || !currentPaper) return;

  userInput.value = "";
  userInput.style.height = "auto";
  setSending(true);

  appendMessage("user", text);
  conversationHistory.push({ role: "user", content: text });

  const typingEl = appendTyping();
  setStatus("loading");

  try {
    const reply = await queryAgent(text);
    typingEl.remove();
    appendMessage("agent", reply);
    conversationHistory.push({ role: "assistant", content: reply });
    setStatus("ready");
  } catch (err) {
    typingEl.remove();
    appendMessage("agent", `Sorry, something went wrong: ${err.message}`);
    setStatus("error");
  } finally {
    setSending(false);
  }
}

// ── Agent query → FastAPI hybrid RAG (sqlite-vec + FTS5) + Claude
async function queryAgent(_userText) {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      arxivId: currentPaper.arxivId,
      title: currentPaper.title || "",
      abstract: currentPaper.abstract || "",
      messages: conversationHistory,
    }),
  });
  const raw = await res.text();
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error(raw.slice(0, 200) || res.statusText);
  }
  if (!res.ok) {
    const d = data.detail;
    const msg =
      typeof d === "string"
        ? d
        : Array.isArray(d)
          ? d.map((e) => e.msg || JSON.stringify(e)).join("; ")
          : JSON.stringify(d);
    throw new Error(msg || res.statusText);
  }
  if (!data.reply || typeof data.reply !== "string") {
    throw new Error("Invalid response from RAG server");
  }
  return data.reply;
}

// ── UI helpers ──────────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Agent";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text; // safe — no innerHTML

  wrapper.appendChild(label);
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function appendTyping() {
  const wrapper = document.createElement("div");
  wrapper.className = "message agent typing";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setStatus(state) {
  statusDot.className = `dot ${state}`;
}

function setSending(sending) {
  sendBtn.disabled = sending;
  userInput.disabled = sending;
}

// Auto-grow textarea
userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
});

