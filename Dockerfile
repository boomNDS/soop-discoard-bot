# Production-ready container for the FastAPI + Discord bot stack.
# Expects a Python project with pyproject.toml and uv.lock.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

# Copy project files needed for build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY scripts ./scripts

# Install dependencies
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Default: run the FastAPI app. Run the bot with: 
# docker run ... uv run python -m src.bot
CMD ["uv", "run", "uvicorn", "soupnotify.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
