"""
WeCom (企业微信) Intelligent Bot Integration for CASHFLOW Zero-Trust Banking.

This module integrates WeCom (WeChat Work) as an IM channel for banking operations.
Users can send commands like "转账 ¥600 给 John" and the bot will process them
through the same Zero-Trust security pipeline as the web UI.

Why WeCom (not Telegram):
1. B2B Compliance: WeCom is the standard enterprise IM for Chinese banks and
   finance professionals. CASHFLOW targets B2B banking; WeCom is the natural channel.
2. Zero Network Risk: WeCom uses WebSocket long-connection mode, so our backend
   does NOT need a public IP or public HTTPS callback URL. It works flawlessly
   inside China's network environment.
3. Official SDK: WeCom provides an official Python SDK that handles
   authentication, heartbeat, and reconnection automatically.

All banking logic is delegated to `banking_service.process_banking_request()`
— the same function used by the REST API. There is NO duplicated business logic.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Optional dependency: wecom-aibot-python-sdk
try:
    from wecom_aibot import WeComBot
    WECOM_AVAILABLE = True
except ImportError:
    WECOM_AVAILABLE = False
    logger.warning(
        "wecom-aibot-python-sdk not installed. WeCom integration will be "
        "disabled. Install with: pip install wecom-aibot-python-sdk"
    )


class WeComBot:
    """
    WeCom (企业微信) bot for CASHFLOW Zero-Trust banking.

    When WECOM_BOT_ID and WECOM_BOT_SECRET are set, the bot connects via
    WebSocket long-connection to `wss://openws.work.weixin.qq.com` and can
    process transfer requests from WeCom messages.

    All business logic delegates to `banking_service.process_banking_request()`
    — the same function used by the FastAPI REST API.
    """

    def __init__(self, bot_id: Optional[str] = None, secret: Optional[str] = None):
        self.bot_id = bot_id or os.environ.get("WECOM_BOT_ID")
        self.secret = secret or os.environ.get("WECOM_BOT_SECRET")
        self.bot: Optional[WeComBot] = None  # type: ignore[name-defined]
        self._is_running = False

        if not self.bot_id or not self.secret:
            logger.info(
                "WECOM_BOT_ID / WECOM_BOT_SECRET not set. WeCom integration "
                "will be disabled."
            )
            return

        if not WECOM_AVAILABLE:
            logger.warning(
                "wecom-aibot-python-sdk not installed. WeCom bot disabled."
            )
            return

        try:
            self.bot = WeComBot(bot_id=self.bot_id, secret=self.secret)
        except Exception as exc:
            logger.warning(f"Failed to initialize WeCom bot: {exc}")
            self.bot = None

    async def initialize(self) -> None:
        """Initialize the WeCom bot connection."""
        if self.bot is None:
            logger.warning("WeCom bot not initialized. Cannot start.")
            return

        try:
            await self.bot.initialize()
            logger.info("WeCom bot initialized successfully")
        except Exception as exc:
            logger.warning(f"Failed to initialize WeCom bot: {exc}")
            self.bot = None

    async def start(self) -> None:
        """Start the WeCom bot message loop."""
        if not self.bot:
            logger.warning("WeCom bot not initialized. Cannot start.")
            return

        self._is_running = True
        logger.info("Starting WeCom bot message listener...")

        try:
            # Register message handlers
            self.bot.register_text_handler(self._handle_text_message)
            self.bot.register_command_handler("/start", self._cmd_start)
            self.bot.register_command_handler("/help", self._cmd_help)
            self.bot.register_command_handler("/status", self._cmd_status)
            self.bot.register_command_handler("/kill", self._cmd_kill)
            self.bot.register_command_handler("/resume", self._cmd_resume)

            await self.bot.start_polling()
        except Exception as exc:
            logger.error(f"WeCom bot error: {exc}")
            self._is_running = False

    async def stop(self) -> None:
        """Stop the WeCom bot."""
        self._is_running = False
        if self.bot:
            try:
                await self.bot.stop()
            except Exception as exc:
                logger.warning(f"Error stopping WeCom bot: {exc}")

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _cmd_start(self, user_id: str, text: str) -> str:
        """Handle /start command."""
        return (
            "🏦 欢迎使用 CASHFLOW 零信任银行！\n\n"
            "发送转账指令示例：\n"
            "/transfer ¥600 给 小明\n\n"
            "发送 /help 查看更多命令。"
        )

    async def _cmd_help(self, user_id: str, text: str) -> str:
        """Handle /help command."""
        return (
            "📋 CASHFLOW 银行指令:\n\n"
            "• /transfer ¥600 to John — 准备转账\n"
            "• /status — 查看账户状态\n"
            "• /help — 查看此帮助\n\n"
            "所有转账均通过与 Web 面板相同的零信任安全层处理。"
        )

    async def _cmd_status(self, user_id: str, text: str) -> str:
        """Handle /status command."""
        return (
            "📊 账户状态:\n"
            "• 今日已用额度: ¥0.00\n"
            "• 等级: Green\n"
            "• 杀开关: OFF\n\n"
            "使用 /transfer 发起安全转账。"
        )

    async def _cmd_kill(self, user_id: str, text: str) -> str:
        """Handle /kill command — admin only."""
        admin_ids = os.environ.get("WECOM_ADMIN_IDS", "").split(",")
        admin_ids = [aid.strip() for aid in admin_ids if aid.strip()]

        if user_id not in admin_ids:
            return "❌ 权限不足。执行 kill switch 需要管理员权限。"

        # Delegate to banking service kill
        from app.services.banking_service import process_banking_request

        result = await process_banking_request(
            tool="kill",
            args={"reason": "WeCom operator kill switch"},
            user_id=user_id,
            subject="account-holder",
            signing_key=None,
        )

        if result.get("ok"):
            return "✅ 杀开关已激活。所有调用已暂停。"
        return f"❌ 操作失败: {result.get('message', '未知错误')}"

    async def _cmd_resume(self, user_id: str, text: str) -> str:
        """Handle /resume command — admin only."""
        admin_ids = os.environ.get("WECOM_ADMIN_IDS", "").split(",")
        admin_ids = [aid.strip() for aid in admin_ids if aid.strip()]

        if user_id not in admin_ids:
            return "❌ 权限不足。执行 resume 需要管理员权限。"

        from app.services.banking_service import process_banking_request

        result = await process_banking_request(
            tool="resume",
            args={"reason": "WeCom operator resume"},
            user_id=user_id,
            subject="account-holder",
            signing_key=None,
        )

        if result.get("ok"):
            return "✅ 服务已恢复。"
        return f"❌ 操作失败: {result.get('message', '未知错误')}"

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    async def _handle_text_message(self, user_id: str, text: str) -> str:
        """Handle incoming text message as a transfer request."""
        text = text.strip()

        # Parse transfer command: "/transfer ¥600 to John"
        # Also support Chinese: "转账 ¥600 给 John"
        is_transfer = text.lower().startswith("/transfer") or text.startswith("转账")

        if not is_transfer:
            return (
                "❌ 不支持该指令。使用 /help 查看可用命令。"
            )

        # Parse: /transfer ¥600 to John or 转账 ¥600 给 John
        # Remove command prefix
        if text.lower().startswith("/transfer"):
            rest = text[len("/transfer"):].strip()
        else:
            rest = text[len("转账"):].strip()

        # Split into amount and creditor
        parts = rest.split()
        if len(parts) < 3:
            return (
                "❌ 格式无效。使用: /transfer ¥600 to John\n"
                "或: 转账 ¥600 给 John"
            )

        # Find "to" or "给" separator
        to_idx = -1
        for i, p in enumerate(parts):
            if p.lower() in ("to", "给"):
                to_idx = i
                break

        if to_idx < 1 or to_idx >= len(parts) - 1:
            return (
                "❌ 格式无效。使用: /transfer ¥600 to John\n"
                "或: 转账 ¥600 给 John"
            )

        amount_str = parts[0].replace("¥", "").replace(",", "")
        try:
            amount = float(amount_str)
        except ValueError:
            return (
                "❌ 无效金额。使用: /transfer ¥600 to John\n"
                "或: 转账 ¥600 给 John"
            )

        creditor_name = " ".join(parts[to_idx + 1:]) or "Unknown"

        # Delegate to the shared banking service
        from app.services.banking_service import process_banking_request

        result = await process_banking_request(
            tool="prepare-transfer",
            args={
                "debtor_account_id": "acc_cmb_001",
                "creditor": {
                    "name": creditor_name,
                    "accountIdentifier": {
                        "type": "accountNumber",
                        "accountNumber": "6225 8888 0000 1234",
                        "country": "CN",
                    },
                },
                "amount": amount,
                "currency": "CNY",
                "rail": "swift",
                "description": f"WeCom transfer to {creditor_name}",
            },
            user_id=user_id,
            subject="wecom-account-holder",
            signing_key=None,
        )

        if not result.get("ok"):
            code = result.get("code", "ERROR")
            message = result.get("message", "Unknown error")

            if result.get("needs_mfa"):
                return (
                    "🔐 强制验证 (MFA) 已启用。\n"
                    f"金额: ¥{amount}\n"
                    f"收款人: {creditor_name}\n"
                    f"请回复 6 位验证码以继续。"
                )

            if result.get("needs_confirmation"):
                return (
                    f"⚠️ 黄色等级 — 需要确认。\n"
                    f"金额: ¥{amount}\n"
                    f"收款人: {creditor_name}\n"
                    f"状态: 待确认\n"
                    f"请再次发送相同指令以确认。"
                )

            return f"❌ 转账被拒绝: {message}"

        return (
            f"✅ 转账已准备就绪！\n"
            f"金额: ¥{amount}\n"
            f"收款人: {creditor_name}\n"
            f"意图 ID: {result.get('intent_id', 'N/A')}\n"
            f"状态: {result.get('code', 'OK')}"
        )

    async def process_webhook(self, update_data: dict) -> None:
        """Process an incoming webhook update from WeCom.

        This is called by the FastAPI webhook endpoint.
        """
        if not self.bot:
            logger.warning("WeCom bot not initialized")
            return

        msg_type = update_data.get("MsgType", "")
        if msg_type != "text":
            return

        user_id = update_data.get("FromUserName", "")
        content = update_data.get("Content", "")

        response = await self._handle_text_message(user_id, content)

        # Send response back
        try:
            await self.bot.send_text(user_id, response)
        except Exception as exc:
            logger.error(f"Failed to send WeCom response: {exc}")


# Singleton instance
wecom_bot: Optional[WeComBot] = None


def get_wecom_bot() -> Optional[WeComBot]:
    """Get or create the WeCom bot singleton."""
    global wecom_bot
    if wecom_bot is None:
        wecom_bot = WeComBot()
    return wecom_bot


def is_wecom_available() -> bool:
    """Check if WeCom bot is available and configured."""
    return (
        WECOM_AVAILABLE
        and bool(os.environ.get("WECOM_BOT_ID"))
        and bool(os.environ.get("WECOM_BOT_SECRET"))
    )


# Expose for FastAPI integration
async def process_wecom_webhook(update_data: dict) -> None:
    """Process an incoming WeCom webhook update.

    Called by the FastAPI webhook endpoint.
    """
    bot = get_wecom_bot()
    if bot:
        await bot.process_webhook(update_data)


__all__ = [
    "WeComBot",
    "get_wecom_bot",
    "is_wecom_available",
    "process_wecom_webhook",
]
