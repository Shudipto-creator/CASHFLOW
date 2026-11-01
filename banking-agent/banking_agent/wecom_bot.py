"""
WeCom (企业微信) Bot for CASHFLOW Zero-Trust Banking Layer.

Provides Ed25519-signed MFA challenge/response and transfer operations via WeChat Work chat.
All banking logic delegates to banking_agent.gate.SecureBankGate — the same code
used by the FastAPI REST API.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Make `banking_agent` importable
REPO_ROOT = Path(__file__).resolve().parents[1]
BANKING_AGENT_DIR = Path(__file__).resolve().parent
if str(BANKING_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(BANKING_AGENT_DIR))

from banking_agent.gate import (  # noqa: E402
    GateClient,
    GateCode,
    SecureBankGate,
    SmsCodeMfa,
    Tier,
    TransferOutcome,
)

logger = logging.getLogger(__name__)

try:
    from wecom_aibot import WeComBot as _WeComBot
except ImportError:
    try:
        from wecom_aibot_python_sdk.core.wecom_bot import WeComBot as _WeComBot
    except ImportError:
        _WeComBot = None


class WeComBot:
    """WeCom (企业微信) bot for CASHFLOW Zero-Trust banking layer."""

    def __init__(self, bot_id: Optional[str] = None, secret: Optional[str] = None):
        import os
        self.bot_id = bot_id or os.environ.get("WECOM_BOT_ID")
        self.secret = secret or os.environ.get("WECOM_BOT_SECRET")
        self._bot = None
        self._is_running = False

        if not self.bot_id or not self.secret:
            logger.info("WECOM_BOT_ID or WECOM_BOT_SECRET not set — WeCom bot disabled")
            self._bot = None
            return

        if _WeComBot is None:
            logger.warning("wecom-aibot-python-sdk not installed — WeCom bot disabled")
            self._bot = None
            return

        try:
            self._bot = _WeComBot(bot_id=self.bot_id, secret=self.secret)
        except Exception as exc:
            logger.warning(f"Failed to initialize WeChat bot: {exc}")
            self._bot = None

        if self._bot is None:
            self._bot_available = False
            logger.warning("WeChat bot is not available")
            return
        self._bot_available = True

    async def initialize(self) -> None:
        if self._bot is None:
            logger.warning("WeChat bot not initialized")
            return
        try:
            await self._bot.initialize()
            logger.info("WeChat bot initialized successfully")
        except Exception as exc:
            logger.warning(f"Failed to initialize WeChat bot: {exc}")
            self._bot = None

    async def start(self) -> None:
        if self._bot is None:
            logger.warning("WeChat bot not initialized")
            return

        self._is_running = True
        logger.info("Starting WeChat bot message listener…")
        try:
            self._bot.register_text_handler(self._handle_text_message)
            self._bot.register_command_handler("/start", self._cmd_start)
            self._bot.register_command_handler("/help", self._cmd_help)
            self._bot.register_command_handler("/status", self._cmd_status)
            self._bot.register_command_handler("/kill", self._cmd_kill)
            self._bot.register_command_handler("/resume", self._cmd_resume)
            await self._bot.start_polling()
        except Exception as exc:
            logger.error(f"WeChat bot error: {exc}")
            self._is_running = False

    async def stop(self) -> None:
        self._is_running = False
        if self._bot:
            try:
                await self._bot.stop()
            except Exception as exc:
                logger.warning(f"Failed to stop WeChat bot: {exc}")

    # ---- command handlers ------------------------------------------------

    async def _cmd_start(self, user_id: str, text: str) -> str:
        return (
            "🏦 欢迎使用 CASHFLOW 零信任银行！\n\n"
            "发送转账指令示例：\n"
            "/transfer ¥600 给 小明\n\n"
            "发送 /help 查看更多命令。"
        )

    async def _cmd_help(self, user_id: str, text: str) -> str:
        return (
            "📋 CASHFLOW 银行指令:\n\n"
            "• /transfer ¥600 to John — 准备转账\n"
            "• /status — 查看账户状态\n"
            "• /help — 查看此帮助\n\n"
            "所有转账均通过与 Web 面板相同的零信任安全层处理。"
        )

    async def _cmd_status(self, user_id: str, text: str) -> str:
        return (
            "📊 账户状态:\n"
            "• 今日已用额度: ¥0.00\n"
            "• 等级: Green\n"
            "• 杀开关: OFF\n\n"
            "使用 /transfer 发起安全转账。"
        )

    async def _cmd_kill(self, user_id: str, text: str) -> str:
        import os

        admin_ids = os.environ.get("WECOM_ADMIN_IDS", "").split(",")
        admin_ids = [aid.strip() for aid in admin_ids if aid.strip()]

        if user_id not in admin_ids:
            return "❌ 权限不足。执行 kill switch 需要管理员权限。"

        from banking_agent.gate import GateClient

        client = GateClient(
            policy=BANKING_AGENT_DIR / "okgate.yaml",
            root=BANKING_AGENT_DIR,
            run_id=f"wecom-kill-{user_id}",
        )
        await client.open()
        try:
            result = await client.kill("WeCom operator kill switch")
        except Exception as exc:
            return f"❌ 操作失败: {exc}"
        finally:
            await client.close()

        if isinstance(result, str) and result.startswith("Kill"):
            return "✅ 杀开关已激活。所有调用已暂停。"
        return f"❌ 操作失败: {result}"

    async def _cmd_resume(self, user_id: str, text: str) -> str:
        import os

        admin_ids = os.environ.get("WECOM_ADMIN_IDS", "").split(",")
        admin_ids = [aid.strip() for aid in admin_ids if aid.strip()]

        if user_id not in admin_ids:
            return "❌ 权限不足。执行 resume 需要管理员权限。"

        from banking_agent.gate import GateClient

        client = GateClient(
            policy=BANKING_AGENT_DIR / "okgate.yaml",
            root=BANKING_AGENT_DIR,
            run_id=f"wecom-resume-{user_id}",
        )
        await client.open()
        try:
            result = await client.resume()
        except Exception as exc:
            return f"❌ 操作失败: {exc}"
        finally:
            await client.close()

        if isinstance(result, str) and result.lower().startswith("resume"):
            return "✅ 服务已恢复。"
        return f"❌ 操作失败: {result}"

    # ------------------------------------------------------------------
    # Message handler
    # ---------------------------------------------------------------------------

    async def _handle_text_message(self, user_id: str, text: str) -> str:
        text = text.strip()
        is_transfer = text.lower().startswith("/transfer") or text.startswith("转账")

        if not is_transfer:
            return "❌ 不支持该指令。使用 /help 查看可用命令。"

        if text.lower().startswith("/transfer"):
            rest = text[len("/transfer"):].strip()
        else:
            rest = text[len("转账"):].strip()

        parts = rest.split()
        if len(parts) < 3:
            return "❌ 格式无效。使用: /transfer ¥600 to John\n或: 转账 ¥600 给 John"

        to_idx = -1
        for i, p in enumerate(parts):
            if p.lower() in ("to", "给"):
                to_idx = i
                break

        if to_idx < 1 or to_idx >= len(parts) - 1:
            return "❌ 格式无效。使用: /transfer ¥600 to John\n或: 转账 ¥600 给 John"

        amount_str = parts[0].replace("¥", "").replace(",", "")
        try:
            amount = float(amount_str)
        except ValueError:
            return "❌ 无效金额。使用: /transfer ¥600 to John\n或: 转账 ¥600 给 John"

        creditor_name = " ".join(parts[to_idx + 1:]) or "Unknown"

        from banking_agent.gate import GateClient, SecureBankGate

        client = GateClient(
            policy=BANKING_AGENT_DIR / "okgate.yaml",
            root=BANKING_AGENT_DIR,
            run_id=f"wecom-transfer-{user_id}",
        )
        await client.open()
        try:
            gate = SecureBankGate(
                client=client,
                subject="wecom-account-holder",
            )
            outcome = await gate.transfer(
                debtor_account_id="acc_cmb_001",
                creditor={
                    "name": creditor_name,
                    "accountIdentifier": {
                        "type": "accountNumber",
                        "accountNumber": "6225 8888 0000 1234",
                        "country": "CN",
                    },
                },
                amount=amount,
                currency="CNY",
                rail="swift",
                description=f"WeCom transfer to {creditor_name}",
            )
        except Exception as exc:
            return f"❌ 转账失败: {exc}"
        finally:
            await client.close()

        if not outcome.ok:
            code = outcome.code or "UNKNOWN"
            message = outcome.message or "Unknown error"
            if outcome.needs_mfa:
                return (
                    "🔐 强制验证 (MFA) 已启用。\n"
                    f"金额: ¥{amount}\n"
                    f"收款人: {creditor_name}\n"
                    f"请回复 6 位验证码以继续。"
                )
            return f"❌ 转账被拒绝: {message} ({code})"

        return (
            f"✅ 转账已准备就绪！\n"
            f"金额: ¥{amount}\n"
            f"收款人: {creditor_name}\n"
            f"意图 ID: {outcome.transfer_intent_id or 'N/A'}\n"
            f"状态: {outcome.code}\n"
        )

    async def process_webhook(self, update_data: dict) -> None:
        if self._bot is None:
            logger.warning("WeChat bot not initialized")
            return
        msg_type = update_data.get("MsgType", "")
        if msg_type != "text":
            return
        user_id = update_data.get("FromUserName", "")
        content = update_data.get("Content", "")
        response = await self._handle_text_message(user_id, content)
        try:
            await self._bot.send_text(user_id, response)
        except Exception as exc:
            logger.error(f"Failed to send WeChat response: {exc}")


wecom_bot: Optional[WeComBot] = None


def get_wecom_bot() -> Optional[WeComBot]:
    global wecom_bot
    if wecom_bot is None:
        wecom_bot = WeComBot()
    return wecom_bot


def is_wecom_available() -> bool:
    import os

    return bool(os.environ.get("WECOM_BOT_ID")) and bool(
        os.environ.get("WECOM_BOT_SECRET")
    )


async def process_wecom_webhook(update_data: dict) -> None:
    bot = get_wecom_bot()
    if bot:
        await bot.process_webhook(update_data)


__all__ = ["WeComBot", "get_wecom_bot", "is_wecom_available", "process_wecom_webhook"]
