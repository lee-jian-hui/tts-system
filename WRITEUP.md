# TTS Gateway – Approach, Design Choices, and Lessons Learned

This write-up summarizes how I approached the TTS gateway assignment, the key architectural and implementation decisions I made, and what I learned while building and iterating on the system.

## 1. Approach & Goals

My overall goal was to treat this as a small but realistic gateway that could plausibly evolve into production, rather than a one-off demo. Concretely, I optimized for:

- **Correct streaming behavior**: low-latency, chunked audio over WebSockets with clear ordering and backpressure semantics.
- **Separation of concerns**: transport, orchestration, providers, and transcoding are clearly separated and testable in isolation.
- **Extensibility**: adding providers or changing storage / transcoding should not require touching the HTTP/WebSocket handlers.

At the same time, I intentionally constrained scope:

- I focused on **two providers** (a mock tone generator and Coqui TTS) and a single frontend demo.
- I kept **storage in-memory**, without external databases, and left **auth/security** out of scope.
- I favored **simple, explicit code** over aggressive optimization, good enough for a local demo and easy to reason about.

## 2. Architecture at a Glance

The system is split into a backend gateway and a browser frontend.

- **Backend (FastAPI)**
  - `app.api` and `app.main` expose REST endpoints (`/v1/tts/sessions`, `/v1/voices`, `/healthz`, `/metrics`) and a WebSocket endpoint (`/v1/tts/stream/{session_id}`).
  - `TTSService` orchestrates provider streaming, retries, circuit-breaking, and session status updates.
  - Providers:
    - `MockToneProvider` generates tones from text as PCM16.
    - `CoquiTTSProvider` wraps the Coqui TTS library, synthesizes a WAV file, and streams its PCM frames.
  - `AudioTranscodeService` uses ffmpeg CLI to convert between formats (`pcm16`, `mulaw`, `opus`, `mp3`, `wav`) and adjust sample rates.
  - An in-memory repository stores `TTSSession` objects; Prometheus metrics and logging middleware provide observability.

- **Frontend (React/Vite)**
  - A simple SPA lets users pick text, provider, and target format.
  - For `pcm16`, it plays audio live via Web Audio as chunks arrive.
  - For `wav`/`mp3`, it monitors the stream, then fetches a full file via an HTTP endpoint and plays it with a standard `<audio>` element.

This layout keeps the gateway logic concentrated in a small number of services, while the frontend is responsible for user experience and basic metrics display (bytes, latency, dropped frames).

## 3. Key Design Choices

### 3.1 Streaming Strategy

**I made streaming the most important concern when designining the whole system**
- Providers expose `async def stream_synthesize(...) -> AsyncIterator[AudioChunk]`, yielding small PCM16 chunks.
- `TTSService.stream_session_audio` is an async generator that:
  - Pulls chunks from the provider stream (with per-chunk timeouts and retry logic),
  - Transcodes each chunk on the fly,
  - Yields encoded bytes to the WebSocket handler as soon as they’re ready.
- The WebSocket handler pushes each encoded chunk to the client as a separate JSON-wrapped message.

For Coqui, we currently use a pragmatic, file‑based streaming approach:

- Instead of generating audio incrementally frame‑by‑frame from the model, we first synthesize the entire utterance into a temporary WAV file. We then stream raw PCM frames from this file to the client, as if they were being produced live. 

- This introduces a small amount of upfront latency (we wait for the utterance to finish synthesizing), and it is not “true” model‑level streaming, but it significantly simplifies the integration.

- By working with a standard WAV file, we can rely on well‑understood file and PCM operations for buffering, backpressure, reconnection, and format handling, rather than implementing custom Coqui‑specific streaming logic. This makes the system easier to reason about, test, and debug at this stage.

The design is intentionally incremental: as we need lower latency, support for very long utterances, or tighter resource constraints, this WAV‑based pipeline can be evolved into a more production‑grade solution that pulls smaller chunks directly from the model. Because the external streaming contract is already based on PCM frames, we can improve the internals over time without forcing changes on downstream consumers.


### 3.2 Chunk Ordering & Protocol

To make ordering explicit and debuggable:

- Every WebSocket audio message includes a monotonically increasing `seq` field: `{"type":"audio","seq":N,"data":"<base64>"}`.
- Within `TTSService.stream_session_audio`, processing is strictly sequential for a given session: fetch one provider chunk, transcode it, send it, then move on to the next.

On the frontend, I use `seq` to:

- Detect gaps (e.g., if `seq` jumps from 5 to 7, one chunk was dropped or missed).
- Track a “dropped frames” metric and surface it in the UI.

This protocol makes it easy to reason about ordering and to spot issues during debugging or demos.

### 3.3 Backpressure

I chose a simple, implicit backpressure mechanism:

- On the server, each call to `await websocket.send_json(...)` in the WebSocket handler acts as a backpressure point. If the client or network slows down, sending takes longer, which naturally slows reading from the provider stream.
- On the client, for live PCM16 playback, I track how far ahead the scheduled playhead is relative to the current time in the Web Audio context. When a “limit buffer” option is enabled and that lead exceeds a threshold (~2 seconds), new chunks are dropped and counted as dropped frames instead of increasing latency indefinitely.

For `wav`/`mp3`, the streaming path is used mainly for metrics, actual playback happens via a single file fetched once the stream ends, so backpressure is less critical to user experience there.

### 3.4 Normalization of Requests (text, voice, language, format)

Inputs from the browser are normalized through Pydantic models and a domain model:

- `CreateTTSSessionRequest` validates:
  - Non-empty `text`,
  - `provider` and `voice` identifiers,
  - `sample_rate_hz > 0`,
  - `target_format` as a fixed union of supported formats,
  - Optional `language` string.
- `TTSSession` stores the normalized fields for each session, making session metadata easy to inspect and use later.

For the assignment, I intentionally kept validation around `voice` and `language` light:

- The gateway does not yet enforce that `voice` belongs to the chosen `provider` or that `language` is strictly supported.
- The mock provider ignores `language`; Coqui uses a configured default and may accept a per-utterance language when the model supports it.

This was a conscious tradeoff between completeness and implementation effort; in a production setting, I would tighten these constraints.

### 3.5 Transcoding (ffmpeg) and Concurrency

For audio conversion, I chose to rely on ffmpeg with python bindings:

- It is widely available, stable, and supports all required formats and resampling.
- Encapsulating ffmpeg calls in `AudioTranscodeService` means other parts of the code never touch format-specific details, and all interaction with the `ffmpeg` process is centralized (build args, feed bytes on stdin, read bytes on stdout, handle errors).

Although ffmpeg itself runs in a separate OS process, the Python call that *waits* for it (`subprocess.run`) is blocking. To keep the asyncio event loop responsive:

- `AudioTranscodeService.transcode_chunk` is an async method that offloads the blocking `_ffmpeg_transcode` call to a worker thread. That worker sits blocked on `subprocess.run` while the main event-loop thread continues serving other coroutines.
- This preserves the async streaming interface while preventing a single transcoding call from freezing the entire event loop, even though the underlying work is still done by an external process.

A more advanced version could use a dedicated transcoding executor or external service, but this approach is adequate for the scale of this assignment.

### 3.6 Extensibility Toward Production

Several aspects of the design aim at making it easy to extend:

- **Provider abstraction**: `BaseTTSProvider` and `ProviderRegistry` decouple gateway logic from specific providers. Adding a new TTS source means implementing a small interface and registering it, without changing routing or streaming code.
- **Service boundaries**: `TTSService`, `AudioTranscodeService`, repositories, and config are separate modules with clear responsibilities. Swapping in a real database or external transcoder would mainly affect those modules.
- **Configuration via env vars**: Provider flags and Coqui settings are read from environment variables, which is the same mechanism you’d use in a real deployment to control behavior across environments.

These choices are intended to keep the codebase flexible if it were to grow into a multi-provider, production-grade gateway.


### 3.7 Approach to Testing

I relied primarily on automated tests at three levels:

- **Unit tests** for `TTSService`, `AudioTranscodeService`, and rate limiting, using `pytest`/`pytest-asyncio` to cover control flow, error handling, and edge cases.
- **Integration tests** that exercise the FastAPI app via `TestClient`, covering HTTP endpoints, WebSocket streaming (including `seq` ordering), and metrics/logging middleware.
- **End-to-end tests** that create sessions and stream audio through the public API for both the mock tone provider and (when available) Coqui, ensuring the main user flows behave correctly.

### 3.8 Frontend Stress Test Mode

As a bonus, I added a simple stress-test mode to the frontend. It reuses the public API to fire many synthetic sessions (configurable total count and concurrency) from the browser, then streams and discards audio while collecting metrics (bytes, chunks, latency, success/failure counts). In parallel, the UI polls the backend `/metrics` endpoint and renders small sparklines for active streams, rate-limit usage, and in-flight stress sessions, which makes it easy to observe how the gateway behaves under load and how rate limiting kicks in without needing an external load-testing tool.


## 4. Lessons Learned

Building this project surfaced a few useful lessons:

- **Streaming is more than just “chunked responses”**  
  Getting true end-to-end streaming required aligning provider APIs, transcoding, and WebSocket behavior. Even small details, like sequence numbers or when to send EOS, have a big impact on debuggability and perceived latency.

- **Blocking work in an async system needs explicit handling**  
  It’s easy to accidentally block the event loop by calling `subprocess.run` or heavy CPU-bound code from async functions. Offloading ffmpeg to a thread and thinking about pool usage reinforced the importance of isolating blocking work in a streaming environment.

- **Observability pays off quickly**  
  Investing in sequence numbers, Prometheus metrics, and basic logging early made it much easier to verify behavior, especially around retries, circuit breaking, and dropped frames.

- **Balancing completeness with pragmatism is key**  
  I deliberately left some areas (language validation, persistent storage, advanced backpressure) at a “good enough for the assignment” level.

- **Frontend and backend streaming must be co-designed**  
  The decision to treat PCM16 as a live stream and `wav`/`mp3` as file-oriented formats meant the frontend needed two different playback paths. This reinforced that streaming design isn’t just a backend concern; client capabilities and UX matter too.

- **Backpressure handling**
  Handling backpressure is inherently tricky because it sits at the intersection of networking, buffering, and user experience. There are many possible strategies (implicit socket backpressure, bounded queues, adaptive throttling, dropping policies, pause/resume protocols, etc.), but choosing and tuning among them only really makes sense once the overall architecture and requirements are clear: target latencies, max utterance lengths, concurrency, failure behavior, and resource limits. For now, a simple, conservative approach is acceptable; as we evolve this into a more production‑grade system, we can introduce explicit queues, clearer flow‑control contracts between components, and more robust policies for what to do when a client or downstream system falls behind.


## 5. Tradeoffs & Future Improvements

If this project were to evolve into a production gateway, there are several clear next steps:

- **Stronger validation and richer metadata**  
  Enforce that voices belong to providers, validate languages more strictly, and expose richer voice metadata (e.g., gender, style, supported languages) in `GET /v1/voices`.

- **Persistent storage and scaling**  
  Move session storage out of memory into a persistent store (e.g., Redis or a database), which would enable horizontal scaling and better observability of session history.

- **Richer transcoding and TTS infrastructure**  
  Consider long-lived ffmpeg pipelines, a separate transcoding service, or GPU-accelerated providers for higher throughput and lower latency, especially for large or concurrent workloads.

- **Auth, Security and governance**  
  Add authentication and authorization, more sophisticated rate limiting (per token or user), and better multi-tenant isolation if used as a shared gateway.

- **Bonus features from the assignment**  
  Explore SSML support, word/phoneme timing markers, and caching/deduplication to reduce repeated work and improve responsiveness.

- **Extending to include more providers**
  this might require some refactors surrounding implement a clean system to register what providers we support, etc. and expose that to the frontend as well

  however the design currently still enables one to easily extend to add a new provider in the backend
  

Overall, the current implementation meets the assignment’s requirements while keeping in mind the extensibility required to evolve beyond a simple local demo
