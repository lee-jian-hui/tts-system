# Session Streaming Queue & Workers

This document explains the bounded in‑process queue used for streaming and how
it interacts with the rest of the gateway.

## Motivation

The heavy part of a TTS session is not `create_session` but streaming:

- Provider synthesis (Coqui, mock tone),
- On‑the‑fly transcoding via ffmpeg,
- WebSocket sends to the client.

To avoid unbounded concurrent streams (and unbounded backlog) inside a single
process, the gateway uses a simple bounded queue + worker pool:

- Limit how many streams can be active at once (workers),
- Limit how many additional streams can be waiting in memory (queue size),
- Fail fast with a structured error when the system is overloaded.

This complements, but does not replace, IP‑based rate limiting at the HTTP
edge.

## Components

- **Streaming queue** – a process‑wide `asyncio.Queue[SessionWorkItem]` with a
  configurable `maxsize` (`SESSION_QUEUE_MAXSIZE`).
- **Workers** – `SESSION_QUEUE_WORKER_COUNT` background tasks started on app
  startup; each repeatedly pulls a `SessionWorkItem` and runs the full
  `TTSService.stream_session_audio` loop, sending chunks and EOS over the
  client's WebSocket.
- **Metrics** – Prometheus gauges and counters:
  - `tts_session_queue_depth` – current queue depth,
  - `tts_session_queue_maxsize` – configured queue capacity,
  - `tts_session_workers_busy` / `tts_session_workers_total` – busy vs total
    workers,
  - `tts_session_queue_full_total` – number of enqueue attempts rejected due
    to a full queue.

## Request Flow

1. Client calls `POST /v1/tts/sessions`:
   - Rate limiter enforces per‑IP request limits.
   - Gateway normalizes the request and calls `TTSService.create_session`
     directly (no queue; this path is cheap).
   - Response includes `session_id` and a `ws_url`.

2. Client opens `WS /v1/tts/stream/{session_id}`:
   - The handler accepts the WebSocket and calls
     `enqueue_stream_request(session_id, websocket)`.
   - If the streaming queue has capacity, a `SessionWorkItem` is added and the
     handler awaits the worker's `Future`.
   - If the queue is full, the handler sends a structured `{"type":"error",
     "code":503,...}` message and closes the WebSocket with a `1013` status
     ("try again later").

3. Worker behaviour:
   - Reads the `SessionWorkItem` from the queue,
   - Increments the `workers_busy` metric and updates queue depth,
   - Streams chunks from `TTSService.stream_session_audio`:
     - Sends `audio` messages,
     - Sends a final `eos` on success,
     - Converts provider/transcoding errors into structured `error` messages,
     - Always closes the WebSocket on terminal errors.
   - Decrements `workers_busy`, marks the item `done`, updates queue depth.

## Tuning

All tuning is via environment variables (`backend/app/config.py`):

- `SESSION_QUEUE_MAXSIZE` – how many streams may be queued in memory waiting
  for a worker. Small values favour fast failure (503) over long queueing.
- `SESSION_QUEUE_WORKER_COUNT` – how many streams may be active concurrently
  inside this gateway process.

In combination, these control how the gateway behaves under load:

- At most `SESSION_QUEUE_WORKER_COUNT` heavy streams run at once,
- At most `SESSION_QUEUE_MAXSIZE` additional streams wait in memory,
- Beyond that, new streams are rejected explicitly, and the stress‑test UI
  surfaces these overload events as `WS 503` failures and bumped queue metrics.

