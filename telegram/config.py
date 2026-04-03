"""Telegram bot configuration."""

import os
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class TelegramConfig:
    """Configuration for Telegram bot."""

    token: str = ""
    api_base_url: str = "http://localhost:8000"
    allowed_users: List[str] = field(default_factory=list)
    admin_users: List[str] = field(default_factory=list)
    max_message_length: int = 4096  # Telegram message limit
    pagination_size: int = 10
    cache_ttl: int = 60  # seconds

    # Webhook settings (optional, for production)
    webhook_url: Optional[str] = None
    webhook_port: int = 8443
    webhook_cert_path: Optional[str] = None

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Create config from environment variables."""
        allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        admin = os.getenv("TELEGRAM_ADMIN_USERS", "")

        return cls(
            token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
            allowed_users=[u.strip() for u in allowed.split(",") if u.strip()],
            admin_users=[u.strip() for u in admin.split(",") if u.strip()],
            webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL"),
            webhook_port=int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443")),
            webhook_cert_path=os.getenv("TELEGRAM_CERT_PATH")
        )

    def is_user_allowed(self, username: str) -> bool:
        """Check if user is allowed to use the bot."""
        if not self.allowed_users:
            return True  # Allow all if no restriction set
        return username in self.allowed_users

    def is_user_admin(self, username: str) -> bool:
        """Check if user has admin privileges."""
        return username in self.admin_users
