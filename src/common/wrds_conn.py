"""One place to open the WRDS connection. The first run asks for your password and a Duo push."""
from __future__ import annotations

from . import config


def connect():
    import wrds

    if not config.WRDS_USERNAME:
        raise SystemExit("Set WRDS_USERNAME in .env first (copy .env.example).")
    return wrds.Connection(wrds_username=config.WRDS_USERNAME)
