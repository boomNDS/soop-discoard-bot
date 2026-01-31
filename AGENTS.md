# Repository Guidelines

## Project Structure & Module Organization
This repository is currently a skeleton. At the moment, it contains:
- `README.md` for a brief project description.
- `LICENSE` for licensing information.

If you add source code, keep it in a dedicated directory such as `src/`. Place configuration files at the repo root, and keep any future assets in an `assets/` or `public/` folder. Add tests under `tests/` or alongside source files using a consistent naming pattern (see Testing Guidelines).

## Build, Test, and Development Commands
No build, test, or run commands are defined yet. If you introduce a runtime (for example, Node.js), document the commands in `README.md` and update this section. Example patterns to follow:
- `npm run dev` – start local development.
- `npm test` – run the test suite.
- `npm run lint` – run formatting/lint checks.

## Coding Style & Naming Conventions
There are no style rules enforced yet. When adding code:
- Use consistent indentation (2 spaces for JS/TS, 4 for Python, etc.) and commit a formatter configuration if applicable (e.g., `prettier`, `eslint`, `ruff`).
- Use clear, descriptive file names and avoid abbreviations in module names.
- Keep directory names lowercase with hyphens when needed (e.g., `src/bot-client`).

## Testing Guidelines
No tests or frameworks are configured. If you add tests:
- Choose a standard framework for the language (e.g., Jest for JS/TS, Pytest for Python).
- Use a predictable naming convention such as `*.test.ts` or `test_*.py`.
- Document how to run tests in `README.md` and in this file.

## Commit & Pull Request Guidelines
Git history currently shows only “Initial commit,” so no convention is established. Use concise, present-tense commit messages (e.g., “Add command handler for ping”).

For pull requests:
- Include a clear description of changes and any manual test steps.
- Link related issues if applicable.
- Add screenshots or logs for user-facing or behavior-changing updates.

## Configuration & Secrets
If the bot requires credentials (tokens, API keys), store them in environment variables and document expected keys in `README.md`. Do not commit secrets to the repository.
