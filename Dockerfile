FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml

FROM python:3.12-slim
ENV PYTHONPATH=/app
ENV DEBIAN_FRONTEND=noninteractive

# Install Python deps first (from builder cache), then supervisor system pkg
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip install --system -r pyproject.toml && \
    apt-get update && apt-get install -y --no-install-recommends supervisor && \
    rm /etc/supervisor/supervisord.conf && \
    rm -rf /var/lib/apt/lists/*

COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY . /app/

RUN mkdir -p /var/log/supervisor

ENTRYPOINT ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
