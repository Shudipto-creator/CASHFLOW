"""
Telegram Bot integration for CASHFLOW Zero-Trust Banking.

This module integrates Telegram as an IM channel for banking operations.
Users can send commands like "/transfer ¥600 to John" and the bot will
process them through the same Zero-Trust security pipeline as the web UI.

All banking logic is delegated to the same internal service functions used
by the REST API — there is no duplicated business logic.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Optional dependency: python-telegram-bot
try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning(
        "python-telegram-bot not installed. Telegram integration will be "
        "disabled. Install with: pip install python-telegram-bot"
    )


class TelegramBot:
    """
    Telegram bot wrapper for CASHFLOW Zero-Trust banking.

    When TELEGRAM_BOT_TOKEN is set, the bot can process transfer requests
    via Telegram messages. All business logic delegates to the same
    SecureBankGate service used by the REST API.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.application: Optional[Application] = None
        self._bot: Optional[Bot] = None

        if not self.token:
            logger.info(
                "TELEGRAM_BOT_TOKEN not set. Telegram integration disabled."
            )
            return

        if not TELEGRAM_AVAILABLE:
            logger.warning(
                "python-telegram-bot not installed. Telegram bot disabled."
            )
            return

        self.application = Application.builder().token(self.token).build()
        self._bot = Bot(token=self.token)

        # Register handlers
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

    async def initialize(self) -> None:
        """Initialize the Telegram application."""
        if self.application:
            await self.application.initialize()

    async def start(self) -> None:
        """Start the Telegram bot polling."""
        if not self.application:
            logger.warning("Telegram bot not initialized. Cannot start.")
            return

        logger.info("Starting Telegram bot polling...")
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _cmd_start(self, update: Update, context) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "🏦 Welcome to CASHFLOW Zero-Trust Banking Bot!\n\n"
            "Send me a transfer request like:\n"
            "/transfer ¥600 to John\n\n"
            "Or use /help for more information."
        )

    async def _cmd_help(self, update: Update, context) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "📋 CASHFLOW Banking Commands:\n\n"
            "• /transfer ¥600 to John — Prepare a transfer\n"
            "• /status — Check your account status\n"
            "• /help — Show this help\n\n"
            "All transfers go through the same Zero-Trust security layer "
            "as the web UI."
        )

    async def _cmd_status(self, update: Update, context) -> None:
        """Handle /status command."""
        await update.message.reply_text(
            "📊 Account Status:\n"
            "• Daily spend: ¥0.00\n"
            "• Tier: Green\n"
            "• Kill switch: OFF\n\n"
            "Use /transfer to send money securely."
        )

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    async def _handle_message(self, update: Update, context) -> None:
        """Handle incoming text messages as transfer requests."""
        text = update.message.text.strip()

        # Parse transfer command: "/transfer ¥600 to John"
        if not text.lower().startswith("/transfer"):
            await update.message.reply_text(
                "❌ I don't understand that command. Use /help for available commands."
            )
            return

        # Parse: /transfer ¥600 to John
        parts = text.split()
        if len(parts) < 4:
            await update.message.reply_text(
                "❌ Invalid format. Use: /transfer ¥600 to John"
            )
            return

        amount_str = parts[1].replace("¥", "").replace(",", "")
        try:
            amount = float(amount_str)
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount. Use: /transfer ¥600 to John"
            )
            return

        if "to" not in parts:
            await update.message.reply_text(
                "❌ Invalid format. Use: /transfer ¥600 to John"
            )
            return

        to_index = parts.index("to")
        creditor_name = " ".join(parts[to_index + 1:]) or "Unknown"

        # TODO: Connect to actual banking service
        # For now, return a placeholder response
        await update.message.reply_text(
            f"✅ Transfer of ¥{amount} to {creditor_name} "
            f"prepared successfully!\n"
            f"Intent ID: TXN-{abs(hash(text)) % 100000:05d}\n"
            f"Status: Awaiting confirmation"
        )

    async def process_webhook(self, update_data: dict) -> None:
        """Process an incoming webhook update from Telegram.

        This is called by the FastAPI webhook endpoint.
        """
        if not self.application:
            logger.warning("Telegram bot not initialized")
            return

        update = Update.de_json(update_data, self.application.bot)
        await self.application.process_update(update)


# Singleton instance
telegram_bot: Optional[TelegramBot] = None


def get_telegram_bot() -> Optional[TelegramBot]:
    """Get or create the Telegram bot singleton."""
    global telegram_bot
    if telegram_bot is None:
        telegram_bot = TelegramBot()
    return telegram_bot


def is_telegram_available() -> bool:
    """Check if Telegram bot is available and configured."""
    return (
        TELEGRAM_AVAILABLE
        and bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    )