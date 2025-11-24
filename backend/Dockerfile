FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for ffmpeg and Coqui TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy just dependency metadata first so dependency installs can be cached
COPY pyproject.toml uv.lock* ./

# Install Python dependencies using uv (reads pyproject.toml / uv.lock)
# Increase HTTP timeout to make large wheels (e.g. torch) more robust to slow
# networks during the image build.
ENV UV_HTTP_TIMEOUT=300
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir .

# Pre-download the Coqui TTS model into the image so containers do not need
# network access at runtime. To avoid depending on the full project source,
# copy only the minimal app config needed for this step.
RUN mkdir -p app
COPY app/__init__.py app/config.py /app/app/
RUN python - << 'EOF'
from app.config import settings
from TTS.api import TTS

if settings.coqui_enabled:
    # Instantiate once to trigger model download into the default cache.
    TTS(model_name=settings.coqui_model_name, progress_bar=False, gpu=False)
EOF

# Now copy the rest of the backend source code
COPY . /app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
