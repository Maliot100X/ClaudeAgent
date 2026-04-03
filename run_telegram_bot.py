#!/usr/bin/env python3
"""
Standalone Telegram Bot Runner

Run with:
    python run_telegram_bot.py

Environment variables:
    TELEGRAM_BOT_TOKEN - Required. Bot token from @BotFather
    API_BASE_URL - Optional. Backend API URL (default: http://localhost:8000)
    TELEGRAM_ALLOWED_USERS - Optional. Comma-separated list of allowed usernames
    TELEGRAM_ADMIN_USERS - Optional. Comma-separated list of admin usernames
"""

import os
import sys
import asyncio
import signal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from telegram import TelegramBotService


async def main():
    """Main entry point."""
    # Check for token
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable is required")
        print("Get a token from @BotFather on Telegram")
        sys.exit(1)

    # Create service
    service = TelegramBotService()

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print("\n🛑 Shutting down Telegram bot...")
        asyncio.create_task(service.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        print("🚀 Starting Telegram Bot Service...")
        print(f"   API Base URL: {service.config.api_base_url}")
        print(f"   Allowed Users: {service.config.allowed_users or 'All'}")
        print(f"   Admin Users: {service.config.admin_users or 'None'}")
        print("\nBot is running. Press Ctrl+C to stop.\n")

        await service.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
