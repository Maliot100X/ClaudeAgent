"""Telegram notifier for broadcasting updates."""

import logging
from typing import List, Optional
from datetime import datetime

from telegram import Bot
from telegram.constants import ParseMode
import aiohttp

from .config import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Broadcast notifications to Telegram users.

    Used by the agent system to send real-time updates:
    - New trading signals
    - Position updates
    - System alerts
    - Performance summaries
    """

    def __init__(
        self,
        token: Optional[str] = None,
        chat_ids: Optional[List[str]] = None,
        config: Optional[TelegramConfig] = None
    ):
        self.config = config or TelegramConfig.from_env()
        self.token = token or self.config.token
        self.chat_ids = chat_ids or []
        self.bot: Optional[Bot] = None

    async def initialize(self) -> None:
        """Initialize the bot."""
        if not self.token:
            raise ValueError("Telegram bot token required")
        self.bot = Bot(token=self.token)

    async def send_signal_alert(
        self,
        symbol: str,
        signal_type: str,
        price: float,
        strength: int,
        reasoning: str,
        chat_id: Optional[str] = None
    ) -> None:
        """Send trading signal alert."""
        if not self.bot:
            return

        # Emoji based on signal
        emoji = "🟢" if "BUY" in signal_type.upper() else "🔴" if "SELL" in signal_type.upper() else "⚪️"
        stars = "⭐" * min(strength, 5)

        message = f"""
{emoji} **Trading Signal Alert**

**{signal_type.upper()}** {symbol}
Price: ${price:,.2f}
Strength: {stars}

🧠 **Reasoning:**
{reasoning[:200]}

🕐 {datetime.utcnow().strftime('%H:%M:%S')} UTC
        """

        await self._send_message(message, chat_id)

    async def send_position_update(
        self,
        symbol: str,
        action: str,
        price: float,
        pnl: Optional[float] = None,
        chat_id: Optional[str] = None
    ) -> None:
        """Send position update notification."""
        if not self.bot:
            return

        action_emoji = {
            "OPEN": "📈",
            "CLOSE": "📉",
            "STOP_LOSS": "🛑",
            "TAKE_PROFIT": "🎯"
        }.get(action, "📊")

        pnl_text = ""
        if pnl is not None:
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            pnl_text = f"\n{pnl_emoji} P&L: ${pnl:,.2f}"

        message = f"""
{action_emoji} **Position Update**

{symbol} - {action}
Price: ${price:,.2f}{pnl_text}

🕐 {datetime.utcnow().strftime('%H:%M:%S')} UTC
        """

        await self._send_message(message, chat_id)

    async def send_system_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        chat_id: Optional[str] = None
    ) -> None:
        """Send system alert."""
        if not self.bot:
            return

        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨"
        }.get(severity.lower(), "ℹ️")

        formatted_message = f"""
{severity_emoji} **{title}**

{message}

🕐 {datetime.utcnow().strftime('%H:%M:%S')} UTC
        """

        await self._send_message(formatted_message, chat_id)

    async def send_daily_summary(
        self,
        total_equity: float,
        day_pnl: float,
        trades_count: int,
        chat_id: Optional[str] = None
    ) -> None:
        """Send daily performance summary."""
        if not self.bot:
            return

        pnl_emoji = "🟢" if day_pnl >= 0 else "🔴"

        message = f"""
📊 **Daily Performance Summary**

Portfolio Value: ${total_equity:,.2f}
{pnl_emoji} Day P&L: ${day_pnl:,.2f} ({(day_pnl/total_equity)*100:+.2f}%)
Trades Executed: {trades_count}

🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
        """

        await self._send_message(message, chat_id)

    async def _send_message(
        self,
        message: str,
        chat_id: Optional[str] = None
    ) -> None:
        """Send message to chat(s)."""
        if not self.bot:
            return

        targets = [chat_id] if chat_id else self.chat_ids

        if not targets:
            logger.warning("No chat IDs configured for notifications")
            return

        for cid in targets:
            try:
                await self.bot.send_message(
                    chat_id=cid,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send notification to {cid}: {e}")

    async def close(self) -> None:
        """Close bot connection."""
        if self.bot:
            await self.bot.session.close()
