from __future__ import annotations

import argparse
from pathlib import Path

from .settings import get_engine
from .logging_utils import get_logger


logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="voice-tts-kr CLI")
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--out", required=True, help="Output audio file path (.wav)")
    parser.add_argument("--voice", default=None, help="Voice id/name (engine-specific)")
    parser.add_argument("--rate", type=float, default=1.0, help="Rate multiplier [0.5, 2.0]")
    parser.add_argument("--pitch", type=float, default=1.0, help="Pitch multiplier [0.5, 2.0]")
    parser.add_argument("--sample-rate", type=int, default=22050, help="Sample rate in Hz")
    parser.add_argument("--format", default="wav", choices=["wav"], help="Audio format")

    args = parser.parse_args(argv)

    engine = get_engine()
    audio_bytes, sample_rate, mime = engine.synthesize(
        text=args.text,
        voice=args.voice,
        rate=args.rate,
        pitch=args.pitch,
        sample_rate=args.sample_rate,
        audio_format=args.format,
    )
    out_path = Path(args.out)
    out_path.write_bytes(audio_bytes)
    logger.info("Wrote %s (%d bytes, %s)", out_path, len(audio_bytes), mime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
