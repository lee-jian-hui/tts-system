from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any, Dict

import requests
import websockets


BASE_URL = "http://localhost:8080"
TEXT = "Hello KeyReply – streaming test!"
PROVIDER_ID = "mock_tone"
VOICE_ID = "en-US-mock-1"
TARGET_FORMAT = "pcm16"
SAMPLE_RATE_HZ = 16000


def create_session() -> Dict[str, Any]:
    """Call POST /v1/tts/sessions and return the JSON response."""
    url = f"{BASE_URL}/v1/tts/sessions"
    payload = {
        "provider": PROVIDER_ID,
        "voice": VOICE_ID,
        "text": TEXT,
        "target_format": TARGET_FORMAT,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "language": "en-US",
    }
    resp = requests.post(url, json=payload, timeout=5)
    resp.raise_for_status()
    return resp.json()


async def stream_audio(ws_url: str, out_path: Path) -> None:
    """Connect to the WebSocket, read all chunks, and write them to a file."""
    print(f"Connecting to WebSocket: {ws_url}")
    audio_buf = bytearray()
    async with websockets.connect(ws_url) as ws:
        while True:
            message = await ws.recv()
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "audio":
                chunk_b64 = data["data"]
                chunk = base64.b64decode(chunk_b64)
                audio_buf.extend(chunk)
                print(f"Received chunk seq={data.get('seq')} size={len(chunk)}")
            elif msg_type == "eos":
                print("Received end-of-stream")
                break
            else:
                print(f"Unknown message type: {msg_type}")

    out_path.write_bytes(audio_buf)
    print(f"Wrote {len(audio_buf)} bytes of PCM16 audio to {out_path}")


def main() -> int:
    print(f"Creating TTS session against {BASE_URL} ...")
    session = create_session()
    session_id = session["session_id"]
    ws_url = session["ws_url"]
    print(f"Session created: {session_id}")

    out_path = Path("stream_output.pcm")
    asyncio.run(stream_audio(ws_url, out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

