# voice-tts-kr – TTS Gateway

This project implements a Text-to-Speech (TTS) API gateway with:

- Multiple providers (mock tone + Coqui TTS),
- A REST API for creating TTS sessions and listing voices,
- A WebSocket endpoint that streams audio chunks in real time,
- On-the-fly audio re-encoding via ffmpeg,
- A React/Vite browser demo frontend.

The goal is to simulate a production-style low-latency media gateway that can be extended with additional providers.

## Project layout

- `backend/` – FastAPI gateway, providers, services, tests.
- `frontend/tts-app/` – React/Vite demo client.
- `docker-compose.yaml` – Orchestrates backend and frontend.

## Running locally (Docker)

You can run the full stack with Docker and docker-compose:

```bash
docker compose build
docker compose up
```

Services:

- Backend: `http://localhost:8080`
- Frontend demo: `http://localhost:5173`

The frontend talks to the backend via the `VITE_TTS_API_BASE_URL` environment variable (set to `http://backend:8080` in `docker-compose.yaml`).

## Running locally (manual)

### Backend

From `backend/`:

```bash
uv run python -m uvicorn app.main:create_app --factory --reload --port 8080
```

Key endpoints:

- `GET /healthz` – health check.
- `GET /v1/voices` – list available voices across providers.
- `POST /v1/tts/sessions` – create a TTS streaming session:

  ```json
  {
    "provider": "mock_tone",
    "voice": "en-US-mock-1",
    "text": "Hello KeyReply!",
    "target_format": "pcm16",
    "sample_rate_hz": 16000,
    "language": "en-US"
  }
  ```

  Response:

  ```json
  {
    "session_id": "<uuid>",
    "ws_url": "ws://localhost:8080/v1/tts/stream/<uuid>"
  }
  ```

- `GET /metrics` – Prometheus metrics.

WebSocket streaming:

- Connect to `/v1/tts/stream/{session_id}` to receive:
  - `{"type":"audio","seq":1,"data":"<base64 audio>"}` frames, and
  - A final `{"type":"eos"}` message.

### Frontend

From `frontend/tts-app/`:

```bash
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Then open `http://localhost:5173` and:

- Enter text,
- Choose provider + format (`pcm16`, `wav`, `mp3`),
- Start a session and listen to the stream,
- Observe live metrics (bytes, chunks, latency, dropped frames).

## Environment variables

Backend provider configuration (`backend/app/config.py`):

- `MOCK_TONE_ENABLED` (default `"1"`)  
  - `"1"` to enable the mock tone provider, `"0"` to disable.
- `COQUI_ENABLED` (default `"1"`)  
  - `"1"` to enable the Coqui TTS provider, `"0"` to disable.
- `COQUI_MODEL_NAME` (default `tts_models/en/ljspeech/tacotron2-DDC`)  
  - Coqui model identifier to load.
- `COQUI_LANGUAGE` (default `"en-US"`)  
  - Language tag used with Coqui where applicable.

Frontend:

- `VITE_TTS_API_BASE_URL`  
  - Base URL for the backend TTS API (e.g. `http://localhost:8080` or `http://backend:8080` in Docker).

## Adding a new provider

At a high level:

1. Implement `BaseTTSProvider` in `backend/app/providers/`:
   - Provide `id`, `list_voices`, and `stream_synthesize(...) -> AsyncIterator[AudioChunk]`.
2. Register it in `ProviderRegistry` (`backend/app/providers/registry.py`).
3. Optionally add a feature flag to `AppConfig` (`backend/app/config.py`) and environment variables.
4. Update docs and tests as needed.


