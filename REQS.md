# KeyReply TTS Gateway Assignment

## Overview

Your task is to design and implement a Text-to-Speech (TTS) API Gateway that connects to multiple TTS providers, streams audio in real-time to a web client over WebSocket, and performs live audio re-encoding between formats. This challenge simulates a real-world engineering problem around building low-latency media infrastructure.

The assignment is meant to test your ability to work with streaming APIs, data transformation, and resilient service design. It is intentionally challenging—expect to iterate.

## Resources & Constraints

- Use only open-source or free tools.
- You do not need any API keys or paid TTS services.
- Implement at least one mock TTS provider that streams pre-recorded or synthesized audio.
- Real providers (AWS Polly, Google TTS, Azure, etc.) are optional for bonus points.
- All code must run locally using Docker or your preferred runtime.
- Deliver a working demo with a browser client.

## Core Requirements

### 1. Providers

- Implement at least two TTS providers (one may be mock).
- Normalize `text` input, `voice`, and `language` fields.
- Support streaming audio chunks.
- For the mock provider, generate tone or stream a static WAV file.

### 2. Gateway REST API

Create a REST endpoint for initiating a TTS session:

- `POST /v1/tts/sessions`

Request body:

```json
{
  "provider": "mock|azure|gcloud|polly",
  "voice": "en-US-JennyNeural",
  "text": "Hello KeyReply!",
  "target_format": "pcm16|mulaw|opus|mp3|wav",
  "sample_rate_hz": 16000
}
```

201 Response:

```json
{
  "session_id": "<uuid>",
  "ws_url": "wss://.../v1/tts/stream/<uuid>"
}
```

Provide additional endpoints for:

- `GET /v1/voices`
- `GET /healthz`
- `GET /metrics`

### 3. WebSocket Streaming

The client connects to:

- `/v1/tts/stream/:session_id`

to receive audio data. The server streams binary frames or JSON-wrapped audio messages:

```json
{"type": "audio", "seq": 1, "data": "<binary>"}
{"type": "eos"}
```

Requirements:

- Stream live as data is received from the provider.
- Maintain ordering and backpressure handling.
- Send `eos` (end of stream) upon completion.

### 4. Audio Transformation

Perform on-the-fly re-encoding to support at least three formats among:

- `pcm16`
- `mulaw`
- `opus`
- `mp3`
- `wav`

Use `ffmpeg` or equivalent libraries for transcoding and resampling.

### 5. Browser Demo

Create a simple webpage to:

- Enter text and select provider + format.
- Start a session and play the streamed audio live.
- Display metrics (bytes, latency, dropped frames).

### 6. Resilience

Implement:

- Timeout and retry per provider.
- Circuit breaker for repeated provider failures.
- Logging and basic Prometheus metrics.
- Rate limiting per IP or token.

### 7. Testing

Include unit tests for:

- Format conversion.
- Chunk sequencing.
- Circuit breaker behavior.

### 8. Packaging

- Provide a `Dockerfile` and `docker-compose.yaml` to run the full stack (gateway, mock TTS, frontend).
- Document environment variables.

## Deliverables

- Source code in a Git repository.
- `README.md` including:
  - Setup & run instructions (Docker or manual).
  - API reference and examples.
  - Architecture overview.
  - Tradeoffs and known issues.
  - How to add a new provider.
- Browser demo running locally (e.g., `http://localhost:3000`).
- Short write-up (1–2 pages) describing your approach, design choices, and lessons learned.

## Acceptance Criteria

- End-to-end demo works locally.
- Audio is streamed in real time via WebSocket.
- Supports 3+ formats with verified re-encoding.
- Mock TTS provider included and functional.
- Backpressure and `eos` are handled correctly.
- Logs, metrics, and rate limits are implemented.

## Bonus Points

- Word/phoneme timing markers.
- SSML support.
- Provider failover mid-stream.
- Audio caching or deduplication.
- Frontend stress test mode.

