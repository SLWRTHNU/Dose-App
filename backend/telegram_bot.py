"""Telegram bot for Dose-App.

Group behaviour:
- Sends dose alerts with an inline Done button.
- Sends a repeat alert if the dose is not acknowledged within 10 minutes.
- Confirms acknowledgement in the group when Done is tapped.

Parent private chat commands:
- /override jb:2|jb:3|jb:4|jb:5|water|juicebox|clear
- /status
- /help
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import chart
import config

logger = logging.getLogger(__name__)

VALID_OVERRIDE_ACTIONS = {"jb:2", "jb:3", "jb:4", "jb:5", "water", "juicebox", "clear"}


# ---------------------------------------------------------------------------
# Message formatting helpers
# ---------------------------------------------------------------------------

def _format_action_label(action: str) -> str:
    """Human-readable label for an action string."""
    if action.startswith("jb:"):
        n = action.split(":")[1]
        return f"{n}x jellybeans"
    if action == "water":
        return "water"
    if action == "juicebox":
        return "juice box"
    return action


def _format_alert_text(action: str, bg: Optional[float], trend: Optional[str], is_repeat: bool) -> str:
    arrow = chart.trend_arrow(trend or "Flat") if trend else "?"
    bg_str = f"{bg:.1f}" if bg is not None else "?"

    if action.startswith("jb:"):
        n = action.split(":")[1]
        emoji = "🍬"
        body = f"Give Senna {n}g ({n}x jellybeans)"
    elif action == "water":
        emoji = "💧"
        body = "Give Senna water"
    elif action == "juicebox":
        emoji = "🧃"
        body = "Give Senna juice box - urgent"
    else:
        emoji = "⚠️"
        body = f"Action required: {action}"

    repeat_tag = " (repeat)" if is_repeat else ""
    return f"{emoji} {body}{repeat_tag}\nBG: {bg_str} mmol/L {arrow}"


# ---------------------------------------------------------------------------
# Alert sending
# ---------------------------------------------------------------------------

async def send_alert(
    app: Application,
    action: str,
    bg: Optional[float],
    trend: Optional[str],
    is_repeat: bool = False,
) -> None:
    """Send or re-send a dose alert to the Telegram group."""
    if not config.TELEGRAM_GROUP_ID:
        logger.error("TELEGRAM: TELEGRAM_GROUP_ID not configured - cannot send alert")
        return

    text = _format_alert_text(action, bg, trend, is_repeat)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Done", callback_data="done")]])

    try:
        await app.bot.send_message(
            chat_id=config.TELEGRAM_GROUP_ID,
            text=text,
            reply_markup=keyboard,
        )
        logger.info("TELEGRAM: alert sent to group: action=%s repeat=%s", action, is_repeat)
    except Exception as exc:
        logger.error("TELEGRAM: failed to send alert: %s", exc)


async def notify_acknowledged(app: Application, acknowledged_by: str, action: str) -> None:
    """Send an acknowledgement confirmation to the Telegram group."""
    if not config.TELEGRAM_GROUP_ID:
        return
    label = _format_action_label(action)
    text = f"✅ Done - logged by {acknowledged_by} ({label})"
    try:
        await app.bot.send_message(chat_id=config.TELEGRAM_GROUP_ID, text=text)
        logger.info("TELEGRAM: ack confirmation sent for action=%s by=%s", action, acknowledged_by)
    except Exception as exc:
        logger.error("TELEGRAM: failed to send ack confirmation: %s", exc)


# ---------------------------------------------------------------------------
# Command and callback handlers
# ---------------------------------------------------------------------------

def _is_parent(chat_id: int) -> bool:
    return str(chat_id) in config.TELEGRAM_PARENT_IDS


async def cb_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline button 'Done' tapped in group chat."""
    query = update.callback_query
    await query.answer()

    state = context.bot_data.get("state")
    if state is None:
        await query.edit_message_text("Error: state not available.")
        return

    username = query.from_user.username or query.from_user.first_name or "unknown"
    snap = state.acknowledge(acknowledged_by=username)

    # Log to Sheets
    try:
        import sheets
        sheets.log_acknowledgement(
            bg=snap["bg"] or 0.0,
            trend=snap["trend"] or "unknown",
            action=snap["action"],
            acknowledged_by=username,
            override_was_active=snap["override_was_active"],
        )
    except Exception as exc:
        logger.error("TELEGRAM: sheets logging failed in cb_done: %s", exc)

    label = _format_action_label(snap["action"])
    await query.edit_message_text(f"✅ Done - logged by {username} ({label})")
    logger.info("TELEGRAM: Done tapped by %s action=%s", username, snap["action"])


async def cmd_override(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/override <action> - set or clear parent override. Parents only."""
    if not _is_parent(update.effective_chat.id):
        await update.message.reply_text("This command is only available to configured parents.")
        return

    state = context.bot_data.get("state")
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage: /override jb:2|jb:3|jb:4|jb:5|water|juicebox|clear"
        )
        return

    action = args[0].lower()
    if action not in VALID_OVERRIDE_ACTIONS:
        await update.message.reply_text(
            f"Unknown action '{action}'. Valid: jb:2 jb:3 jb:4 jb:5 water juicebox clear"
        )
        return

    # Also call /override endpoint internally to keep state consistent.
    if action == "clear":
        state.set(override_action=None)
        await update.message.reply_text("Override cleared.")
        logger.info("TELEGRAM: override cleared by %s", update.effective_user.username)
    else:
        state.set(override_action=action)
        label = _format_action_label(action)
        await update.message.reply_text(f"Override set: {label}")
        logger.info("TELEGRAM: override set to '%s' by %s", action, update.effective_user.username)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status - show current BG, trend, action, cooldown. Parents only."""
    if not _is_parent(update.effective_chat.id):
        await update.message.reply_text("This command is only available to configured parents.")
        return

    state = context.bot_data.get("state")
    if state is None:
        await update.message.reply_text("Error: state not available.")
        return

    snap = state.get_snapshot()
    now = datetime.now(timezone.utc)

    bg_str = f"{snap['bg']:.1f}" if snap["bg"] is not None else "unknown"
    trend_raw = snap["trend"] or "unknown"
    arrow = chart.trend_arrow(trend_raw)
    effective_action = snap["override_action"] or snap["active_dose"] or "none"
    cooldown_active = snap["cooldown_until"] is not None and now < snap["cooldown_until"]
    override_active = snap["override_action"] is not None

    lines = [
        f"BG: {bg_str} mmol/L {arrow}",
        f"Action: {effective_action}",
        f"Cooldown: {'yes' if cooldown_active else 'no'}",
        f"Override: {'yes - ' + snap['override_action'] if override_active else 'no'}",
        f"Last updated: {snap['last_updated'].strftime('%H:%M:%S UTC') if snap['last_updated'] else 'never'}",
    ]
    await update.message.reply_text("\n".join(lines))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help - list available commands."""
    text = (
        "Dose-App commands (parents only):\n"
        "/override jb:2|jb:3|jb:4|jb:5|water|juicebox - set manual dose override\n"
        "/override clear - clear override\n"
        "/status - show current BG, trend, action, cooldown\n"
        "/help - show this message"
    )
    await update.message.reply_text(text)


# ---------------------------------------------------------------------------
# Bot lifecycle
# ---------------------------------------------------------------------------

async def start(state) -> Application:
    """Build and start the Telegram bot. Returns the running Application."""
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set - cannot start bot")

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.bot_data["state"] = state

    application.add_handler(CallbackQueryHandler(cb_done, pattern="^done$"))
    application.add_handler(CommandHandler("override", cmd_override))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("help", cmd_help))

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    logger.info("TELEGRAM: bot started and polling")
    return application


async def stop(app: Application) -> None:
    """Gracefully stop the Telegram bot."""
    try:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("TELEGRAM: bot stopped")
    except Exception as exc:
        logger.error("TELEGRAM: error during shutdown: %s", exc)
