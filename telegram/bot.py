"""Enhanced Telegram bot with complete command handlers."""

import os
import logging
from typing import Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import aiohttp

from .config import TelegramConfig
from .handlers import CommandHandlers
from .formatters import MessageFormatters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for controlling the AI Agent Platform."""

    def __init__(
        self,
        token: Optional[str] = None,
        api_base_url: str = "http://localhost:8000",
        allowed_users: Optional[list] = None
    ):
        self.config = TelegramConfig(
            token=token or os.getenv("TELEGRAM_BOT_TOKEN"),
            api_base_url=api_base_url,
            allowed_users=allowed_users or []
        )
        self.handlers = CommandHandlers(self.config)
        self.formatters = MessageFormatters()
        self.application: Optional[Application] = None

    async def initialize(self) -> None:
        """Initialize the bot application."""
        if not self.config.token:
            raise ValueError("Telegram bot token is required")

        self.application = Application.builder().token(self.config.token).build()
        self._register_handlers()

        logger.info("Telegram bot initialized")

    def _register_handlers(self) -> None:
        """Register all command handlers."""
        if not self.application:
            return

        # Basic commands
        self.application.add_handler(CommandHandler("start", self.handlers.start))
        self.application.add_handler(CommandHandler("help", self.handlers.help))
        self.application.add_handler(CommandHandler("status", self.handlers.status))

        # Agent commands
        self.application.add_handler(CommandHandler("agents", self.handlers.agents))

        # AI Provider commands
        self.application.add_handler(CommandHandler("models", self.handlers.models))
        self.application.add_handler(CommandHandler("provider", self.handlers.provider))
        self.application.add_handler(CommandHandler("test_provider", self.handlers.test_provider))

        # Strategy commands
        self.application.add_handler(CommandHandler("strategies", self.handlers.strategies))
        self.application.add_handler(CommandHandler("run_strategy", self.handlers.run_strategy))
        self.application.add_handler(CommandHandler("stop_strategy", self.handlers.stop_strategy))

        # Data commands
        self.application.add_handler(CommandHandler("signals", self.handlers.signals))
        self.application.add_handler(CommandHandler("positions", self.handlers.positions))
        self.application.add_handler(CommandHandler("logs", self.handlers.logs))

        # Wallet tracking commands
        self.application.add_handler(CommandHandler("wallet", self.handlers.wallet))
        self.application.add_handler(CommandHandler("add_wallet", self.handlers.add_wallet))
        self.application.add_handler(CommandHandler("remove_wallet", self.handlers.remove_wallet))
        self.application.add_handler(CommandHandler("wallet_tokens", self.handlers.wallet_tokens))
        self.application.add_handler(CommandHandler("wallet_pnl", self.handlers.wallet_pnl))

        # Token discovery commands
        self.application.add_handler(CommandHandler("new_tokens", self.handlers.new_tokens))
        self.application.add_handler(CommandHandler("trending", self.handlers.trending_tokens))
        self.application.add_handler(CommandHandler("meme_coins", self.handlers.meme_coins))

        # Dashboard
        self.application.add_handler(CommandHandler("dashboard", self.handlers.dashboard))

        # Callback queries for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handlers.handle_callback))

        # Error handler
        self.application.add_error_handler(self._error_handler)

    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in the bot."""
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )

    async def start(self) -> None:
        """Start the bot."""
        if not self.application:
            await self.initialize()

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)

        logger.info("Telegram bot started")

        # Send startup notification to channel if configured
        await self._send_startup_notification()

    async def _send_startup_notification(self) -> None:
        """Send startup notification to configured channel."""
        channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
        if not channel_id or not self.application:
            return

        try:
            await self.application.bot.send_message(
                chat_id=channel_id,
                text="🤖 **AI Agent Platform Started**\n\n"
                     "Bot is now online and ready to receive commands.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")

    async def stop(self) -> None:
        """Stop the bot."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")

    def run(self) -> None:
        """Run the bot (blocking)."""
        import asyncio

        try:
            asyncio.run(self._run_blocking())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except SystemExit:
            logger.info("System exit")

    async def _run_blocking(self) -> None:
        """Internal blocking run method."""
        await self.start()

        try:
            while True:
                import asyncio
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self.stop()


class TelegramBotService:
    """Service wrapper for running bot in production."""

    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config or TelegramConfig.from_env()
        self.bot = TelegramBot(
            token=self.config.token,
            api_base_url=self.config.api_base_url,
            allowed_users=self.config.allowed_users
        )
        self._running = False

    async def start(self) -> None:
        """Start the bot service."""
        await self.bot.initialize()
        await self.bot.start()
        self._running = True

        logger.info("Telegram bot service started")

    async def stop(self) -> None:
        """Stop the bot service."""
        await self.bot.stop()
        self._running = False

    async def health_check(self) -> dict:
        """Health check for the bot service."""
        return {
            "service": "telegram_bot",
            "running": self._running,
            "initialized": self.bot.application is not None,
            "timestamp": datetime.utcnow().isoformat()
        }


if __name__ == "__main__":
    # Run standalone
    config = TelegramConfig.from_env()
    bot = TelegramBot(
        token=config.token,
        api_base_url=config.api_base_url,
        allowed_users=config.allowed_users
    )
    bot.run()
