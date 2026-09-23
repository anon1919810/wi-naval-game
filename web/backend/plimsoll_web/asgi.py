"""Production ASGI entrypoint; never imported by unit tests without settings."""

from .config import Settings
from .main import create_app


app = create_app(Settings.from_env())
