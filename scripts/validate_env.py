import os
import sys

REQUIRED_API = ["SOOP_API_BASE_URL", "SOOP_CLIENT_ID", "DATABASE_URL"]
REQUIRED_BOT = REQUIRED_API + ["DISCORD_TOKEN", "DISCORD_APPLICATION_ID"]


def check(required: list[str]) -> None:
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        sys.stderr.write(f"Missing required env vars: {', '.join(missing)}\n")
        sys.exit(1)


def main() -> None:
    mode = os.getenv("ENV_VALIDATE_MODE", "bot")
    if mode == "api":
        check(REQUIRED_API)
    else:
        check(REQUIRED_BOT)


if __name__ == "__main__":
    main()
