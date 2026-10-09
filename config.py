"""Shared config helpers: load .env and connect to Vespa (local Docker or Vespa Cloud).

Usage:
    from config import load_env, connect_vespa
    load_env()                      # .env values go into os.environ (.env wins over the shell)
    vespa_application = connect_vespa()   # picks local or cloud from VESPA_MODE
"""

import os
from pathlib import Path

from vespa.application import Vespa

ROOT = Path(__file__).parent


def load_env(path: Path | str | None = None) -> None:
    """Load `KEY=value` / `export KEY=value` lines from .env into os.environ."""
    env_file = Path(path) if path else ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip("\"'")


def connect_vespa(mode: str | None = None) -> Vespa:
    """Return a Vespa client for `mode` (`local` or `cloud`); defaults to VESPA_MODE from .env."""
    load_env()
    mode = (mode or os.environ.get("VESPA_MODE", "local")).lower()
    if mode == "local":
        return Vespa(
            url=os.environ.get("VESPA_LOCAL_URL", "http://localhost"),
            port=int(os.environ.get("VESPA_LOCAL_PORT", "8080")),
        )
    if mode == "cloud":
        cert_dir = Path(os.environ["VESPA_CERT_DIR"]).expanduser()
        return Vespa(
            os.environ["VESPA_CLOUD_ENDPOINT"],
            cert=str(cert_dir / "data-plane-public-cert.pem"),
            key=str(cert_dir / "data-plane-private-key.pem"),
        )
    raise ValueError(f"VESPA_MODE must be 'local' or 'cloud', got {mode!r}")
