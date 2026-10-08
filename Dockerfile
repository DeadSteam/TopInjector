FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
# Install dependencies only: the project itself is a flat layout and runs from /app.
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . /app/
ENV PYTHONPATH=/app
# Console scripts are not copied from the builder, so run entry points as modules.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn main:app --host 0.0.0.0 --port 8000"]
