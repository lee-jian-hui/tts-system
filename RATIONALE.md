# RATIONALE – Design & Tradeoffs

This document explains the main design choices for the TTS gateway, with a focus on streaming behavior, ordering, backpressure, normalization, and extensibility toward a production‑grade system.

## 1. Architecture Overview & Design Choices

The gateway is structured around a clear separation of concerns:

- **Transport & API layer**  
  FastAPI (`app.main`, `app.api`) exposes REST endpoints for session management and a WebSocket endpoint for streaming audio. This layer is intentionally thin and delegates business logic to services.

- **Orchestration layer (`TTSService`)**  
  `TTSService` coordinates provider selection, session lifecycle, retries, and circuit‑breaker checks. It owns the streaming pipeline from provider chunks to encoded bytes.

- **Provider layer**  
  Providers (`MockToneProvider`, `CoquiTTSProvider`) implement a common `BaseTTSProvider` protocol and stream raw `AudioChunk` objects. They encapsulate provider‑specific concerns (Coqui model loading, tone synthesis) so the rest of the system doesn’t depend on provider internals.

- **Transcoding layer (`AudioTranscodeService`)**  
  A dedicated service is responsible for format conversion and resampling using ffmpeg. All providers emit a common base format (PCM16), and the transcoder converts into the requested `target_format`.

- **Session and metrics infrastructure**  
  A simple in‑memory repository tracks `TTSSession` objects, while Prometheus metrics (`app.metrics`) and logging middleware provide visibility into behavior and failures.

The overarching design goal is a *streaming‑first* architecture: audio is produced and consumed as an async sequence of small chunks, avoiding large intermediate buffers at the gateway.

## 2. Ordering of Audio Chunks

Chunk ordering is enforced at two levels:

- **Monotonic sequence numbers**  
  The WebSocket handler wraps each encoded chunk in a JSON envelope with a strictly increasing `seq` field:  
  `{"type": "audio", "seq": N, "data": "<base64>"}`. The server increments `seq` once per chunk and never reuses or skips sequence numbers in the normal path.

- **Single sequential pipeline per session**  
  For each session, `TTSService.stream_session_audio` runs a single `async for` pipeline: it pulls one chunk from the provider, transcodes it, sends it over WebSocket, then moves to the next. Chunks for a given session are never processed in parallel, which keeps ordering trivial to reason about and avoids reordering bugs.

On the frontend, `App.tsx` uses the `seq` field to detect any gaps and track dropped frames, providing an additional sanity check on ordering.

## 3. Backpressure Handling

Backpressure is handled in a deliberately simple, end‑to‑end way:

- **Server‑side backpressure via `await`**  
  In the WebSocket handler, each chunk send is `await websocket.send_json(...)`. If the client or network is slow, this `await` stalls, which in turn delays the next `await` on the provider stream. That means the provider is naturally backpressured by the client’s ability to receive data, without explicit queues.

- **Client‑side backpressure and buffering**  
  For PCM16 live playback, the frontend schedules each chunk into a Web Audio `AudioContext` and tracks how far the playhead is ahead of real time. When the lead exceeds a threshold (≈2 seconds) and the “limit live buffer” option is enabled, new chunks are dropped and counted as dropped frames. This avoids unbounded latency growth in the live playback buffer.

  For container formats (`wav`, `mp3`), the client simply accumulates all chunk bytes until EOS, then assembles a single `Blob` for playback. Backpressure here mainly manifests as memory usage and total download time, which is acceptable for the demo scope.

- **Tradeoffs**  
  This backpressure story is intentionally basic: it couples each session’s producer and consumer linearly and does not attempt sophisticated adaptive rate control or buffering strategies. In a higher‑throughput production system, bounded queues, drop policies, or transcoding buffers could be introduced per session or per connection.

## 4. Normalization of Request Fields

Incoming requests from the browser are normalized in two steps: validation at the API boundary and persistence in a domain model.

- **Request validation (`CreateTTSSessionRequest`)**  
  The REST handler for `POST /v1/tts/sessions` accepts a `CreateTTSSessionRequest` Pydantic model. It enforces:
  - Non‑empty `text`,
  - Required `provider` and `voice` identifiers,
  - `sample_rate_hz > 0`,
  - `target_format` restricted to a small `AudioFormat` union (`"pcm16"`, `"mulaw"`, `"opus"`, `"mp3"`, `"wav"`),
  - Optional `language` as a BCP‑47 style string.

- **Session normalization (`TTSSession`)**  
  After validation, `TTSService.create_session` copies these fields into a `TTSSession` domain object, which becomes the single source of truth for a streaming session’s metadata. This makes it easy to look up and reason about sessions without re‑parsing request bodies.

- **Voice and language handling**  
  The current implementation keeps validation light: it assumes the chosen `voice` and `language` are meaningful for the provider, but it does not yet enforce that `voice` belongs to the given `provider` or that `language` is supported. The mock provider ignores language; Coqui uses a configured default and may use a per‑utterance language parameter for multi‑language models.

This design balances correctness and flexibility for the assignment: inputs are strongly typed enough to avoid obvious errors, while leaving room for providers to interpret language and voice details as they see fit.

## 5. Extensibility Toward Production

Several design choices were made to keep the gateway evolvable beyond this assignment:

- **Provider abstraction and registry**  
  The `BaseTTSProvider` protocol defines a small, focused interface (`id`, `list_voices`, `stream_synthesize`). `ProviderRegistry` is responsible for instantiating and exposing providers. Adding a new provider involves implementing the protocol and registering it; the TTS and WebSocket layers remain unchanged.

- **Layered services**  
  Responsibilities are split across services:
  - `TTSService` handles orchestration, retries, and circuit‑breaker integration.
  - `AudioTranscodeService` owns all ffmpeg interactions and format conversions.
  - Repositories encapsulate how sessions are stored (currently in‑memory but easily swappable for a DB).

  This structure allows individual concerns to be replaced or scaled independently: for example, moving from local ffmpeg calls to a remote transcoding microservice would primarily affect the transcoder, not the rest of the stack.

- **Configuration and feature flags**  
  Provider availability and basic parameters (e.g., Coqui model name/language) are driven by environment variables via `app.config`. This pattern scales naturally as more providers or provider‑specific tuning knobs are introduced.

- **Threaded ffmpeg execution**  
  The blocking ffmpeg CLI is wrapped so it runs outside the main event loop. For the assignment, the implementation uses Python’s threading primitives; in a production system, this could evolve into a dedicated transcoding executor or even a separate pool of worker processes behind a queue.

Overall, the intent is that the architecture can grow toward a multi‑provider, multi‑instance gateway without having to rewrite core APIs or the public contract.

## 6. Resilience & Fault Handling

Resilience is addressed at several layers:

- **Timeouts and retries**  
  `TTSService._stream_from_provider_with_retry` wraps each `stream_synthesize` iteration in `asyncio.wait_for` with a configurable timeout. If a provider fails or times out before emitting any audio, the service retries up to a configured number of attempts. Once any audio has been produced, further failures end the stream without retry to avoid duplicated audio.

- **Circuit breaker**  
  A simple circuit breaker (`CircuitBreakerRegistry`) tracks failures per provider and moves between closed, open, and half‑open states based on error rates and timeouts. Before calling a provider, `TTSService.stream_session_audio` consults the breaker; if the circuit is open, the request is rejected immediately. This prevents a misbehaving provider from repeatedly degrading the system.

- **Rate limiting**  
  The `RateLimiter` applies per‑IP limits to `POST /v1/tts/sessions`, protecting the gateway from excessive session creation by a single client.

- **Error propagation and logging**  
  HTTP handlers raise `HTTPException` with appropriate status codes; the WebSocket handler sends `{"type": "error", ...}` messages and closes the connection with suitable codes for client or server errors. Centralized logging captures request paths, status codes, durations, and stack traces for easier debugging.

These mechanisms are intentionally simple but mirror patterns used in production systems, making it straightforward to deepen or tune them as needed.

## 7. Performance & Streaming Tradeoffs

The behavior of the system reflects a set of pragmatic tradeoffs:

- **Use of ffmpeg CLI**  
  ffmpeg is invoked via the CLI because it is well‑tested, widely available, and flexible enough to cover the required formats (`pcm16`, `mulaw`, `opus`, `mp3`, `wav`). Centralizing all transcoding in `AudioTranscodeService` simplifies reasoning about performance and errors.

- **Per‑chunk transcoding vs long‑lived pipelines**  
  Each provider chunk is transcoded independently rather than piping a continuous stream through a dedicated ffmpeg process. This simplifies error handling and implementation at the cost of some startup overhead per chunk. For the assignment scale and local demo, this overhead is acceptable.

- **Provider tradeoffs**  
  - `MockToneProvider` is CPU‑light, relies only on in‑memory operations, and is ideal for tests and basic demos.  
  - `CoquiTTSProvider` synthesizes full utterances to a temporary WAV file and then streams frames. This simplifies integration with the Coqui library but introduces an initial latency spike before streaming starts. For a production deployment, a truly streaming TTS provider or a different integration mode could reduce this latency.

For higher concurrency or stricter latency targets, the next steps would include tuning thread pools or executors, exploring long‑lived ffmpeg processes, or externalizing transcoding to dedicated workers.

## 8. Testing & Validation Strategy

Confidence in behavior comes from a mix of unit, integration, and end‑to‑end tests:

- **Unit tests** focus on:
  - Transcoding correctness (valid WAV headers, decodable MP3 output),
  - Error handling for unsupported formats,
  - Circuit breaker state transitions and rate limiter behavior.

- **Integration tests** verify:
  - HTTP API wiring (`/v1/tts/sessions`, `/v1/voices`, `/metrics`),
  - WebSocket sequencing (`seq` increments and EOS semantics).

- **End‑to‑end tests** exercise:
  - Full flows using the mock provider across multiple formats,
  - Streaming to completion with EOS and reasonable chunk counts.

Manual validation with the Dockerized stack and the React frontend complements automated tests, particularly for subjective aspects like perceived latency and audio quality.

## 9. Known Limitations & Future Work

Several limitations are intentionally left in place to keep the implementation scoped to the assignment:

- **Language support**  
  The gateway does not strictly validate that a given `language` is supported by a provider. The mock provider ignores language entirely; Coqui uses a configured default and may or may not honor per‑utterance language hints depending on the model.

- **State and storage**  
  Sessions are stored in‑memory, which works for a single backend instance but does not survive restarts or support horizontal scaling. Moving to a persistent store (e.g., Redis or a database) would be a natural production step.

- **Resource isolation**  
  Transcoding and synthesis run inside the same container and process as the API. Under heavier loads, separating these concerns (e.g., dedicated transcoding workers, GPU‑enabled TTS workers) would improve robustness.

- **Security and auth**  
  Authentication and authorization are not implemented, as they are out of scope for the assignment. A production gateway would need proper auth, rate limits tied to identities, and stronger input validation.

- **Advanced features**  
  Bonus features like SSML support, word/phoneme timings, and caching are not implemented but could be layered on top of the existing provider and orchestration abstractions.

These limitations are documented so that future work can prioritize the most impactful improvements if the project evolves beyond the current scope.

