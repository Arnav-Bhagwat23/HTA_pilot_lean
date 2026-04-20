from __future__ import annotations

import os
from pathlib import Path


def load_local_env(env_path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from a local .env file without overwriting env vars."""
    path = env_path or Path.cwd() / ".env"
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_openai_api_key() -> str | None:
    load_local_env()
    return os.environ.get("OPENAI_API_KEY")
