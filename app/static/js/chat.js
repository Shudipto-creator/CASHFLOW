/* CASHFLOW chat.js - Ask CASHFLOW streaming client. */

const CHAT = (() => {
  let eventSource = null;
  let container = null;
  let currentMessage = null;
  let currentContent = "";

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function appendMessage(role, html) {
    const div = document.createElement("div");
    div.className = "chat-message " + role;
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    bubble.innerHTML = html;
    div.appendChild(bubble);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  function startStream(url) {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(url);
    eventSource.onopen = () => {};
    eventSource.onmessage = (ev) => {
      try { const data = JSON.parse(ev.data); if (data.text) appendText(data.text); } catch (_) {}
    };
    eventSource.addEventListener("token", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (!currentMessage) {
          currentMessage = appendMessage("assistant", "");
          currentContent = "";
        }
        currentContent += data.text || "";
        currentMessage.querySelector(".chat-bubble").textContent = currentContent;
        container.scrollTop = container.scrollHeight;
      } catch (_) {}
    });
    eventSource.addEventListener("done", () => {
      currentMessage = null; currentContent = "";
      if (eventSource) { eventSource.close(); eventSource = null; }
    });
    eventSource.addEventListener("error", () => {
      if (eventSource) { eventSource.close(); eventSource = null; }
      currentMessage = null; currentContent = "";
    });
  }

  function init(form, streamUrl) {
    if (!form) return;
    container = document.getElementById("chat-history");
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const input = form.querySelector("input, textarea");
      const q = encodeURIComponent(input.value);
      appendMessage("user", escapeHtml(input.value));
      input.value = "";
      startStream(streamUrl + "?q=" + q);
    });
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("ask-form");
  const streamUrl = form ? form.getAttribute("data-stream") : null;
  CHAT.init(form, streamUrl);
});
