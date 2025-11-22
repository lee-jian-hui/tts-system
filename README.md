# voice-tts-kr

Minimal MVP for a Korean TTS service scaffold. This provides:

- A pluggable TTS engine interface
- A dummy local engine that generates simple WAV audio (tone-encoded text)
- FastAPI HTTP endpoints to synthesize speech and list voices
- A CLI to synthesize to a file

This is meant as a foundation to swap in a real Korean TTS backend (e.g., Piper, Coqui TTS) later.

## Quickstart

1) Create a virtual environment and install requirements:

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2) Run the API server:

```
uvicorn app.main:app --reload --port 8080
```

3) Synthesize with the API:

```
curl -X POST http://localhost:8080/synthesize \
  -H 'Content-Type: application/json' \
  -o out.wav \
  -d '{"text":"안녕하세요, 테스트입니다.", "format":"wav", "sample_rate":22050}'
```

4) Or use the CLI:

```
python -m voice_tts_kr.cli --text "안녕하세요, 테스트입니다." --out out.wav --rate 1.0 --pitch 1.0 --sample-rate 22050
```

## Project layout

```
```

## Notes

- The dummy engine encodes text as tones and is not real TTS. It is intentionally dependency-light and offline so you can validate the API/CLI flow. Swap it with a real engine by implementing `BaseTTSEngine` and updating `settings.py`.
- Default format is WAV (16-bit PCM). Adjust `sample_rate`, `rate`, and `pitch` as needed.

## Adding a real TTS engine later


