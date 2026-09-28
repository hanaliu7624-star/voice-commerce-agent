(() => {
  const messagesEl = document.getElementById("messages");
  const statusEl = document.getElementById("status");
  const customerBadge = document.getElementById("customerBadge");
  const form = document.getElementById("composer");
  const textInput = document.getElementById("textInput");
  const sendBtn = document.getElementById("sendBtn");
  const micBtn = document.getElementById("micBtn");
  const muteToggle = document.getElementById("muteToggle");

  let sessionId = null;
  let busy = false;
  let mediaRecorder = null;
  let mediaStream = null;
  let chunks = [];
  let currentAudio = null;

  function setStatus(text, kind = "") {
    statusEl.textContent = text || "";
    statusEl.className = "status" + (kind ? ` ${kind}` : "");
  }

  function setBusy(next) {
    busy = next;
    sendBtn.disabled = next;
    textInput.disabled = next;
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      micBtn.disabled = next;
    }
  }

  function appendBubble(role, text, meta) {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    const roleLabel = role === "user" ? "你" : "客服";
    const metaHtml = meta
      ? `<div class="meta">${meta}</div>`
      : "";
    div.innerHTML = `<span class="role">${roleLabel}</span><div class="text"></div>${metaHtml}`;
    div.querySelector(".text").textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function playAudioBase64(b64, mime) {
    if (!b64 || muteToggle.checked) return;
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
    const src = `data:${mime || "audio/mpeg"};base64,${b64}`;
    currentAudio = new Audio(src);
    currentAudio.play().catch(() => {
      /* 浏览器可能拦截自动播放；用户点过麦克风/发送后通常允许 */
    });
  }

  function formatMeta(data) {
    const parts = [];
    if (data.intent) parts.push(`intent=${data.intent}`);
    if (data.action) parts.push(`action=${data.action}`);
    if (data.order_id) parts.push(`order=${data.order_id}`);
    if (data.trace_id) parts.push(`trace=${data.trace_id}`);
    return parts.join(" · ");
  }

  async function ensureSession() {
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `创建会话失败 (${res.status})`);
    }
    const data = await res.json();
    sessionId = data.session_id;
    customerBadge.textContent = `账号 ${data.customer_id}`;
    appendBubble("bot", data.greeting);
    setStatus("可以说或打字提问。按住「按住说话」录音，松开后发送。");
  }

  async function sendText(text) {
    if (!sessionId || busy) return;
    const trimmed = text.trim();
    if (!trimmed) return;
    appendBubble("user", trimmed);
    textInput.value = "";
    setBusy(true);
    setStatus("回答中…");
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          text: trimmed,
          speak: !muteToggle.checked,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `请求失败 (${res.status})`);
      }
      appendBubble("bot", data.answer, formatMeta(data));
      playAudioBase64(data.audio_base64, data.audio_mime);
      setStatus("就绪");
    } catch (err) {
      setStatus(err.message || String(err), "error");
      appendBubble("bot", "请求失败，请稍后重试。");
    } finally {
      setBusy(false);
      textInput.focus();
    }
  }

  async function sendVoiceBlob(blob) {
    if (!sessionId || busy) return;
    setBusy(true);
    setStatus("识别中…");
    try {
      const formData = new FormData();
      formData.append("session_id", sessionId);
      formData.append("speak", String(!muteToggle.checked));
      const ext = blob.type.includes("mp4") ? "mp4" : "webm";
      formData.append("audio", blob, `recording.${ext}`);
      const res = await fetch("/api/voice", {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `语音请求失败 (${res.status})`);
      }
      appendBubble("user", data.transcript || "（未识别到文字）");
      appendBubble("bot", data.answer, formatMeta(data));
      playAudioBase64(data.audio_base64, data.audio_mime);
      setStatus("就绪");
    } catch (err) {
      setStatus(err.message || String(err), "error");
      appendBubble("bot", "语音处理失败，请改用文字，或再试一次。");
    } finally {
      setBusy(false);
    }
  }

  function pickMimeType() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
    ];
    for (const type of candidates) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return "";
  }

  async function startRecording() {
    if (busy || (mediaRecorder && mediaRecorder.state === "recording")) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("当前浏览器不支持麦克风录音，请用文字，或换 Chrome / Edge。", "error");
      return;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickMimeType();
      chunks = [];
      mediaRecorder = mimeType
        ? new MediaRecorder(mediaStream, { mimeType })
        : new MediaRecorder(mediaStream);
      mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunks.push(ev.data);
      };
      mediaRecorder.onstop = async () => {
        micBtn.setAttribute("aria-pressed", "false");
        micBtn.textContent = "按住说话";
        if (mediaStream) {
          mediaStream.getTracks().forEach((t) => t.stop());
          mediaStream = null;
        }
        const type = mediaRecorder.mimeType || "audio/webm";
        const blob = new Blob(chunks, { type });
        chunks = [];
        if (blob.size < 200) {
          setStatus("录音太短，请按住多说一会儿。", "error");
          return;
        }
        await sendVoiceBlob(blob);
      };
      mediaRecorder.start();
      micBtn.setAttribute("aria-pressed", "true");
      micBtn.textContent = "松开发送";
      setStatus("录音中…松开按钮结束", "recording");
    } catch (err) {
      setStatus("无法使用麦克风：请允许浏览器权限后重试。", "error");
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    sendText(textInput.value);
  });

  micBtn.addEventListener("mousedown", (ev) => {
    ev.preventDefault();
    startRecording();
  });
  micBtn.addEventListener("mouseup", (ev) => {
    ev.preventDefault();
    stopRecording();
  });
  micBtn.addEventListener("mouseleave", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") stopRecording();
  });
  micBtn.addEventListener("touchstart", (ev) => {
    ev.preventDefault();
    startRecording();
  }, { passive: false });
  micBtn.addEventListener("touchend", (ev) => {
    ev.preventDefault();
    stopRecording();
  });

  ensureSession().catch((err) => {
    setStatus(err.message || String(err), "error");
  });
})();
