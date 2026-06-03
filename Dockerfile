FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

RUN uv pip install --system -e .

EXPOSE 8000
