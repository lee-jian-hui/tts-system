FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for ffmpeg and Coqui TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy backend sources
COPY . /app

# Install Python dependencies using uv (reads pyproject.toml / uv.lock)
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir .

# Pre-download the Coqui TTS model into the image so containers do not need
# network access at runtime. This uses the configured COQUI_MODEL_NAME.
RUN python - << 'EOF'
from app.config import settings
from TTS.api import TTS

if settings.coqui_enabled:
    # Instantiate once to trigger model download into the default cache.
    TTS(model_name=settings.coqui_model_name, progress_bar=False, gpu=False)
EOF

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
