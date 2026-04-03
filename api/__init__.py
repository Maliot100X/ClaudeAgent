"""API module for AI Agent Platform."""

from .main import app, create_app
from .telegram_routes import router

__all__ = ["app", "create_app", "router"]
