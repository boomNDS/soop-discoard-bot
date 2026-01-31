# Contributing Guide

Thanks for your interest in contributing!

## Ways to Help

- Implement the Discord bot commands and event handlers.
- Add the SOOP polling service and notification pipeline.
- Improve deployment, observability, and docs.

## Development Setup

1) Install Python 3.12+ and `uv`.
2) Create a `.env` file (see `README.md`).
3) Install dependencies:

```bash
uv sync
```

4) Run the API:

```bash
uv run uvicorn soupnotify.app.main:app --host 0.0.0.0 --port 8000
```

5) Run the bot:

```bash
uv run python -m soupnotify.bot
```

Set `SHARD_COUNT` if you need Discord sharding for large server counts.

## Branch & Commit Style

- Use short, present-tense commits (e.g., "Add link command").
- Keep PRs focused and easy to review.

## Testing

Run tests with:

```bash
uv run pytest
```

## Migrations

Apply migrations:

```bash
uv run alembic upgrade head
```

## Security

Do not commit secrets. Use environment variables instead.
