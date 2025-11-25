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
- `GET /v1/tts/sessions/{session_id}/file?format=wav|mp3|pcm16` – fetch a full audio file for a completed session (used by the frontend for WAV/MP3 playback).

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
- For `pcm16` target format, the frontend plays chunks live via the Web Audio API as they arrive.
- For `wav`/`mp3`, the frontend still consumes the stream for metrics, but playback happens via a single file fetched from `/v1/tts/sessions/{session_id}/file`.

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

The frontend also exposes an **experimental stress-test panel** that can fire
multiple synthetic sessions (configurable total sessions and max concurrency)
against the backend. Audio from these runs is not played; instead, the UI
collects metrics (success/failure counts, bytes/chunks) and polls the backend
`/metrics` endpoint to visualize active streams, rate-limit usage, and
rate-limit window timing as small inline charts.

**Frontend metrics (single session + stress mode)**

- **Bytes received / Chunks** – number of bytes and chunks of audio received
  over the WebSocket for the current run. In stress mode this is aggregated
  across all synthetic sessions.
- **First chunk latency** – time from clicking "Start" to receiving the first
  `audio` chunk, measured in the browser.
- **Dropped frames (network/backend)** – counts chunks that the client did not
  see due to seq gaps or parse errors (i.e., chunks that were missing from the
  stream as observed on the frontend).
- **Dropped frames (playback/frontend)** – counts chunks that arrived but were
  intentionally not played (e.g., when the live PCM buffer is already >2s
  ahead) or failed to enqueue into Web Audio.
- **Stress failures by cause** – in stress mode, a small histogram of the most
  common failure reasons, such as `HTTP 429` (rate limited at session creation),
  `WS 503` (streaming queue full / gateway overloaded), or `WS transport error`
  (WebSocket-level failures).
- **Stress test summary** – shows how many synthetic sessions completed vs
  failed for the latest stress run.

**Backend / load metrics (from Prometheus)**

These are sampled from `/metrics` during a stress run and rendered as text plus
small sparklines:

- **Active streams** – current `tts_active_streams` across providers (how many
  streams the gateway believes are active).
- **Sessions completed / failed** – cumulative session counters from the backend.
- **Rate-limit usage** – `tts_rate_limit_max_bucket_usage` (0–100%), showing how
  full the busiest per-IP rate-limit bucket is relative to its configured
  maximum.
- **Rate-limit window remaining** – seconds until the current IP's
  rate-limit window resets (derived from
  `tts_rate_limit_window_remaining_seconds`).
- **Session queue depth** – number of streaming jobs currently queued in the
  in-process streaming queue (not yet being processed by a worker).
- **Session queue maxsize** – configured maximum queue size.
- **Workers busy / total** – how many streaming worker tasks are currently
  processing jobs vs the total configured worker count.
- **Queue-full events** – total number of times the streaming queue was full
  when a new stream was enqueued; these correspond to `WS 503` errors in stress
  mode.

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

Rate limiting and session queue configuration (`backend/app/config.py`):

- `RATE_LIMIT_MAX_REQUESTS_PER_WINDOW` (default `50`)  
  - Maximum number of `POST /v1/tts/sessions` allowed per IP within a single
    rate-limit window.
- `RATE_LIMIT_WINDOW_SECONDS` (default `60`)  
  - Duration of the rate-limit window in seconds.
- `SESSION_QUEUE_MAXSIZE` (default `100`)  
  - Maximum number of session-creation requests that can be queued in memory.
    When this queue is full, new session creation attempts return HTTP `503`.
- `SESSION_QUEUE_WORKER_COUNT` (default `8`)  
  - Number of background worker tasks that process the in-memory session queue.

Frontend:

- `VITE_TTS_API_BASE_URL`  
  - Base URL for the backend TTS API (e.g. `http://localhost:8080` or `http://backend:8080` in Docker).

## Adding a new provider

To add another TTS provider (e.g. a cloud API):

1. **Implement the provider class**
   - Create a new file in `backend/app/providers/` (for example, `my_provider.py`).
   - Implement a class that follows the `BaseTTSProvider` contract:
     - `id: str` – a stable identifier (e.g. `"my_provider"`).
     - `async def list_voices(self) -> list[ProviderVoice]` – return voices with `id`, `name`, `language`, `sample_rate_hz`, and `base_format` (typically `"pcm16"`).
     - `async def stream_synthesize(self, *, text: str, voice_id: str, language: str | None = None) -> AsyncIterator[AudioChunk]` – yield small `AudioChunk` PCM chunks for the request.

2. **Wire it into the registry**
   - Update `backend/app/providers/registry.py` to instantiate your provider and include it in:
     - `list_providers()`,
     - Provider lookup by `id`.
   - Optionally, guard it with a feature flag (env var) if it requires credentials or heavy dependencies.

3. **Expose configuration**
   - Add any provider-specific config to `backend/app/config.py` (e.g. API keys, base URLs, default language).
   - Document the relevant environment variables in this README.

4. **Update tests**
   - Add unit tests that exercise `list_voices` and `stream_synthesize` for the new provider.
   - Optionally extend integration/e2e tests to cover a simple end-to-end flow with the provider enabled.

5. **Frontend behavior**
   - The frontend discovers providers/voices via `GET /v1/voices`, so as long as your provider returns voices, it should appear automatically in the dropdown.

## Tradeoffs and Known Issues

- **Streaming vs. file playback**
  - `pcm16` is streamed end-to-end and played live in the browser via Web Audio.
  - `wav` and `mp3` are streamed for observability (seq, bytes, latency), but the actual user playback uses a second request to `/v1/tts/sessions/{session_id}/file` to obtain a single valid audio file.

- **Backpressure model**
  - Backpressure is handled implicitly by sequential `await websocket.send_json(...)` calls per session.
  - This is simple and correct, but a slow client or network directly slows provider consumption and transcoding for that session. A production system might add an explicit bounded queue between encoding and the WebSocket.

- **Blocking ffmpeg calls**
  - ffmpeg runs as an external process; the Python call that waits for it (`subprocess.run`) is blocking.
  - To avoid blocking the event loop, transcoding is offloaded to a worker thread, which is sufficient for this assignment but could be evolved into a dedicated transcoding pool or service for higher loads.

- **Provider behavior and latency**
  - `CoquiTTSProvider` synthesizes the full utterance to a temporary WAV and then streams it, which adds an initial latency spike before the first chunk. This simplifies integration with Coqui at the cost of some startup time.

- **Language and voice validation**
  - Requests carry `voice` and optional `language`, but the gateway currently does only light validation: it assumes the combination is meaningful for the provider.
  - The mock provider ignores `language`; Coqui uses a configured default and may accept a per-utterance language. A production gateway would likely enforce that voices belong to providers and that languages are supported.

- **In-memory storage**
  - Sessions are stored in memory, which is fine for local demos but does not survive restarts or support horizontal scaling in terms of a multi-instance, multi-cluster setting. A real deployment would replace this with persistent storage (e.g. Redis or a database).
