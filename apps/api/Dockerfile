FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates build-essential \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
  && mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
COPY ouroboros_api ./ouroboros_api
RUN uv sync --no-dev

ENV OUROBOROS_DB_URL=sqlite+aiosqlite:////app/data/ouroboros.sqlite \
    OUROBOROS_DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "ouroboros_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
