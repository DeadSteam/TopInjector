FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /bin/uv

ENV PYTHONPATH=/app \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# Locked runtime dependencies first (cached unless pyproject.toml / uv.lock change); supervisor is one of them
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY . /app/

# Run as an unprivileged user instead of root.
RUN useradd --system --no-create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /opt/venv
USER appuser

ENTRYPOINT ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
