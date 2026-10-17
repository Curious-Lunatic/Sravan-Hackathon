import os
from pathlib import Path


def load_env() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_api_key() -> str:
    load_env()
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        raise RuntimeError("SARVAM_API_KEY is missing. Paste it into .env.")
    return key
