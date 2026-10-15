# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY ml/pyproject.toml ml/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
RUN uv sync --frozen --package vericlue-api --no-dev --no-install-workspace
COPY ml/src ml/src
COPY services/api/src services/api/src
RUN uv sync --locked --package vericlue-api --no-dev --no-editable

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 \
    CHROMAPULSE_CONFIG=/app/config/chromapulse.json \
    ML_MODELS_CONFIG=/app/ml/configs/models.yaml \
    CALIBRATORS_DIR=/app/ml/configs/calibrators
RUN useradd --uid 10001 --create-home api && mkdir -p /media /models /data && chown api:api /media
COPY --from=builder /app/.venv /app/.venv
COPY services/api/alembic.ini services/api/alembic.ini
COPY services/api/migrations services/api/migrations
COPY packages/contracts/chromapulse.json /app/config/chromapulse.json
COPY ml/configs /app/ml/configs
USER api
EXPOSE 8000
CMD ["sh", "-c", "alembic -c services/api/alembic.ini upgrade head && exec uvicorn vericlue_api.main:app --host 0.0.0.0 --port 8000"]
