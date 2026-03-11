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
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy source and install package only
COPY . .
RUN uv pip install --system --no-cache --no-deps -e .

EXPOSE 8000

CMD ["uvicorn", "talker.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
