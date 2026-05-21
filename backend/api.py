import asyncio
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, request

import chart
import sheets

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Set by main.py before the Flask thread starts.
_state = None


def set_state(state) -> None:
    global _state
    _state = state


def check_auth() -> bool:
    # TODO: swap to token auth - check Authorization header against DOSE_APP_API_TOKEN env var
    return True


@app.route("/status", methods=["GET"])
def get_status():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    if _state is None:
        return jsonify({"error": "service not ready"}), 503

    snap = _state.get_snapshot()
    now = datetime.now(timezone.utc)
    cooldown_active = snap["cooldown_until"] is not None and now < snap["cooldown_until"]
    effective_action = snap["override_action"] or snap["active_dose"]
    trend_raw = snap["trend"] or "Flat"

    return jsonify({
        "action":         effective_action if effective_action else None,
        "bg":             snap["bg"],
        "trend":          trend_raw,
        "trend_arrow":    chart.trend_arrow(trend_raw),
        "cooldown_active": cooldown_active,
        "cooldown_until": snap["cooldown_until"].isoformat() if snap["cooldown_until"] else None,
        "override_active": snap["override_action"] is not None,
        "last_updated":   snap["last_updated"].isoformat() if snap["last_updated"] else None,
    })


@app.route("/acknowledge", methods=["POST"])
def post_acknowledge():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    if _state is None:
        return jsonify({"error": "service not ready"}), 503

    body = request.get_json(silent=True) or {}
    acknowledged_by = body.get("acknowledged_by", "unknown")

    snap = _state.acknowledge(acknowledged_by=acknowledged_by)

    # Log to Sheets - errors are non-fatal but loud.
    try:
        sheets.log_acknowledgement(
            bg=snap["bg"] or 0.0,
            trend=snap["trend"] or "unknown",
            action=snap["action"],
            acknowledged_by=acknowledged_by,
            override_was_active=snap["override_was_active"],
        )
    except Exception as exc:
        logger.error("ACKNOWLEDGE: sheets logging raised unexpectedly: %s", exc)

    # Schedule Telegram notification in the asyncio event loop.
    if _state.event_loop and _state.bot_app:
        import telegram_bot
        try:
            asyncio.run_coroutine_threadsafe(
                telegram_bot.notify_acknowledged(
                    _state.bot_app, acknowledged_by, snap["action"]
                ),
                _state.event_loop,
            )
        except Exception as exc:
            logger.error("ACKNOWLEDGE: failed to schedule Telegram notification: %s", exc)

    return jsonify({"ok": True})


@app.route("/override", methods=["POST"])
def post_override():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    if _state is None:
        return jsonify({"error": "service not ready"}), 503

    body = request.get_json(silent=True) or {}
    action = body.get("action", "")

    if action == "clear":
        _state.set(override_action=None)
        logger.info("OVERRIDE: cleared via API")
    else:
        valid = {"water", "juicebox", "jb:2", "jb:3", "jb:4", "jb:5"}
        if action not in valid:
            return jsonify({"error": f"invalid action '{action}', must be one of {sorted(valid)} or 'clear'"}), 400
        _state.set(override_action=action)
        logger.info("OVERRIDE: set to '%s' via API", action)

    return jsonify({"ok": True})
