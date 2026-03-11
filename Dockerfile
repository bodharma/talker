FROM python:3.12-slim

# Runtime dependencies for WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached until pyproject.toml changes)
COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml && \
    uv pip install --system --no-cache torch --index-url https://download.pytorch.org/whl/cpu

# Copy source and install package only
COPY . .
RUN uv pip install --system --no-cache --no-deps -e .

# Bake LiveKit plugin models (Silero VAD, turn detector) into the image
RUN python -m talker.livekit_agent download-files

EXPOSE 8000

CMD ["uvicorn", "talker.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
