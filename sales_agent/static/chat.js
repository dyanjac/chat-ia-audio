const messagesEl = document.getElementById("messages");
const dateDividerEl = document.getElementById("dateDivider");
const modelSelectEl = document.getElementById("modelSelect");
const refreshModelsBtnEl = document.getElementById("refreshModelsBtn");
const messageInputEl = document.getElementById("messageInput");
const sendBtnEl = document.getElementById("sendBtn");
const recordBtnEl = document.getElementById("recordBtn");
const statusMessageEl = document.getElementById("statusMessage");
const recordingTimeEl = document.getElementById("recordingTime");

let mediaRecorder = null;
let mediaStream = null;
let recordedChunks = [];
let recordingInterval = null;
let recordingStartedAt = null;
let isRecording = false;

function setStatus(message, isError = false) {
  statusMessageEl.textContent = message;
  statusMessageEl.classList.toggle("error", isError);
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function setTodayDivider() {
  dateDividerEl.textContent = formatDate(new Date().toISOString());
}

function appendMessage(role, content, createdAt, audioUrl = null, isTyping = false) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const contentEl = document.createElement("div");
  if (isTyping) {
    contentEl.className = "typing-indicator";
    contentEl.innerHTML = "<span></span><span></span><span></span>";
  } else {
    contentEl.textContent = content;
  }
  bubble.appendChild(contentEl);

  if (audioUrl) {
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = audioUrl;
    bubble.appendChild(audio);
  }

  const meta = document.createElement("div");
  meta.className = "bubble-meta";
  meta.textContent = formatTime(createdAt);
  bubble.appendChild(meta);

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
  return row;
}

async function loadModels() {
  try {
    const response = await fetch("/api/models");
    if (!response.ok) {
      throw new Error("No se pudieron cargar los modelos.");
    }

    const data = await response.json();
    modelSelectEl.innerHTML = "";
    const models = data.models || [];
    const fallbackModel = data.default_model || "";
    const finalModels = models.includes(fallbackModel)
      ? models
      : [fallbackModel, ...models].filter(Boolean);

    for (const model of finalModels) {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      modelSelectEl.appendChild(option);
    }

    if (fallbackModel) {
      modelSelectEl.value = fallbackModel;
    }

    setStatus("Modelos cargados correctamente.");
  } catch (error) {
    setStatus(error.message || "Error cargando modelos.", true);
  }
}

async function sendTextMessage() {
  const message = messageInputEl.value.trim();
  const model = modelSelectEl.value.trim();

  if (!message) {
    setStatus("Escribe un mensaje antes de enviar.", true);
    return;
  }

  appendMessage("user", message, new Date().toISOString());
  messageInputEl.value = "";
  const typingRow = appendMessage("assistant", "", new Date().toISOString(), null, true);
  setStatus("Consultando al asistente...");

  try {
    const response = await fetch("/api/chat/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, model }),
    });

    const data = await response.json();
    typingRow.remove();

    if (!response.ok) {
      throw new Error(data.detail || "No se pudo procesar el mensaje.");
    }

    appendMessage(
      "assistant",
      data.assistant_message.content,
      data.assistant_message.created_at,
      data.assistant_message.audio_url
    );
    setStatus("Respuesta recibida.");
  } catch (error) {
    typingRow.remove();
    setStatus(error.message || "Error enviando mensaje.", true);
  }
}

function updateRecordingClock() {
  const elapsedMs = Date.now() - recordingStartedAt;
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  recordingTimeEl.textContent = `Grabando ${minutes}:${seconds}`;
}

async function startRecording() {
  if (isRecording) {
    return;
  }

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(mediaStream);
    recordedChunks = [];

    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    });

    mediaRecorder.addEventListener("stop", sendRecordedAudio);
    mediaRecorder.start();
    recordingStartedAt = Date.now();
    isRecording = true;
    updateRecordingClock();
    recordingInterval = setInterval(updateRecordingClock, 250);
    recordBtnEl.classList.add("recording");
    recordBtnEl.textContent = "Suelta para enviar";
    setStatus("Grabando audio...");
  } catch (error) {
    setStatus("No se pudo acceder al microfono.", true);
  }
}

function stopRecording() {
  if (!isRecording) {
    return;
  }

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }

  isRecording = false;
  clearInterval(recordingInterval);
  recordingInterval = null;
  recordingTimeEl.textContent = "";
  recordBtnEl.classList.remove("recording");
  recordBtnEl.textContent = "Mantener para grabar";
}

async function sendRecordedAudio() {
  const model = modelSelectEl.value.trim();
  const durationMs = Date.now() - recordingStartedAt;
  recordingStartedAt = null;

  if (durationMs < 700) {
    setStatus("El audio es demasiado corto.", true);
    recordedChunks = [];
    return;
  }

  const blob = new Blob(recordedChunks, { type: "audio/webm" });
  recordedChunks = [];

  const typingRow = appendMessage("assistant", "", new Date().toISOString(), null, true);
  setStatus("Enviando audio...");

  try {
    const formData = new FormData();
    formData.append("file", blob, "audio.webm");
    formData.append("model", model);

    const response = await fetch("/api/chat/audio", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    typingRow.remove();

    if (!response.ok) {
      throw new Error(data.detail || "No se pudo procesar el audio.");
    }

    appendMessage(
      "user",
      data.transcription || data.user_message.content,
      data.user_message.created_at
    );
    appendMessage(
      "assistant",
      data.assistant_message.content,
      data.assistant_message.created_at,
      data.assistant_message.audio_url
    );
    setStatus("Audio procesado correctamente.");
  } catch (error) {
    typingRow.remove();
    setStatus(error.message || "Error enviando audio.", true);
  }
}

sendBtnEl.addEventListener("click", sendTextMessage);
messageInputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendTextMessage();
  }
});

recordBtnEl.addEventListener("pointerdown", async (event) => {
  event.preventDefault();
  await startRecording();
});

["pointerup", "pointerleave", "pointercancel"].forEach((eventName) => {
  recordBtnEl.addEventListener(eventName, () => {
    stopRecording();
  });
});

refreshModelsBtnEl.addEventListener("click", loadModels);

setTodayDivider();
loadModels();
appendMessage(
  "assistant",
  "Laboratorio listo. Puedes escribir o mantener presionado el boton de grabacion para probar el flujo conversacional.",
  new Date().toISOString()
);
