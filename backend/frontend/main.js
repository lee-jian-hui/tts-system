const BASE_URL = "http://localhost:8080";

const form = document.getElementById("tts-form");
const statusEl = document.getElementById("status");
const bytesEl = document.getElementById("bytes");
const chunksEl = document.getElementById("chunks");
const audioEl = document.getElementById("player");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  statusEl.textContent = "Creating session...";
  audioEl.src = "";
  bytesEl.textContent = "0";
  chunksEl.textContent = "0";

  const payload = {
    provider: document.getElementById("provider").value,
    voice: document.getElementById("voice").value,
    text: document.getElementById("text").value,
    target_format: document.getElementById("target-format").value,
    sample_rate_hz: Number(document.getElementById("sample-rate").value),
    language: "en-US",
  };

  try {
    const resp = await fetch(`${BASE_URL}/v1/tts/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const body = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${body}`);
    }
    const { session_id, ws_url } = await resp.json();
    statusEl.textContent = `Session ${session_id} created. Connecting WebSocket...`;
    await streamAudio(ws_url, payload.target_format);
  } catch (err) {
    console.error(err);
    statusEl.textContent = `Error: ${err}`;
  }
});

async function streamAudio(wsUrl, targetFormat) {
  const ws = new WebSocket(wsUrl);
  let chunks = [];
  let totalBytes = 0;

  statusEl.textContent = "Streaming audio...";

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "audio") {
      const chunkBytes = base64ToBytes(msg.data);
      chunks.push(chunkBytes);
      totalBytes += chunkBytes.length;
      bytesEl.textContent = String(totalBytes);
      chunksEl.textContent = String(chunks.length);
    } else if (msg.type === "eos") {
      statusEl.textContent = "Stream complete. Building audio blob...";
      ws.close();
      const mime =
        targetFormat === "mp3"
          ? "audio/mpeg"
          : targetFormat === "wav"
          ? "audio/wav"
          : "audio/raw";
      const blob = new Blob(chunks, { type: mime });
      audioEl.src = URL.createObjectURL(blob);
      audioEl
        .play()
        .then(() => {
          statusEl.textContent = "Playing.";
        })
        .catch(() => {
          statusEl.textContent = "Ready (click play).";
        });
    }
  };

  ws.onerror = (event) => {
    console.error("WebSocket error", event);
    statusEl.textContent = "WebSocket error.";
  };

  ws.onclose = () => {
    if (statusEl.textContent.startsWith("Streaming")) {
      statusEl.textContent = "WebSocket closed unexpectedly.";
    }
  };
}

function base64ToBytes(b64) {
  const binary = atob(b64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

