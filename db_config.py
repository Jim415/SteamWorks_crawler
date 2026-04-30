"""
Shared database configuration for SteamWorks crawler scripts.
"""

import os
from pathlib import Path


def _load_env_file():
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_db_config():
    _load_env_file()

    required = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError(f"Missing required database environment variables: {', '.join(missing)}")

    return {
        "host": os.environ["MYSQL_HOST"],
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "database": os.environ.get("MYSQL_DATABASE", "steamworks_crawler"),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
    }
