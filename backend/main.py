"""Dose-App backend entry point.

Runs three concurrent components:
- Flask REST API in a daemon thread
- Nightscout polling loop (every 5 minutes) as an asyncio task
- Repeat-alert watchdog (every 60 seconds) as an asyncio task
- Telegram bot via python-telegram-bot's async updater
"""

import asyncio
import logging
import signal
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import config
import chart
import nightscout
import telegram_bot
import api as flask_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared application state
# ---------------------------------------------------------------------------

class AppState:
    """Thread-safe shared state. All fields protected by _lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Latest BG reading
        self.bg: Optional[float] = None
        self.trend: Optional[str] = None
        self.last_updated: Optional[datetime] = None

        # Dose state machine
        self.active_dose: Optional[str] = None     # chart-derived action
        self.override_action: Optional[str] = None # parent-set override (takes priority)

        # Alert tracking (for repeat-alert logic)
        self.alert_pending: bool = False            # True = alerted but not yet acknowledged
        self.last_alert_sent: Optional[datetime] = None
        self.last_alerted_dose: Optional[str] = None

        # Cooldown (900 s after each acknowledgement)
        self.cooldown_until: Optional[datetime] = None
        self.cooldown_trigger_action: Optional[str] = None

        # Set by main() after the asyncio loop is running
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.bot_app = None  # telegram.ext.Application

    def get_snapshot(self) -> dict:
        with self._lock:
            return dict(
                bg=self.bg,
                trend=self.trend,
                last_updated=self.last_updated,
                active_dose=self.active_dose,
                override_action=self.override_action,
                alert_pending=self.alert_pending,
                last_alert_sent=self.last_alert_sent,
                cooldown_until=self.cooldown_until,
                cooldown_trigger_action=self.cooldown_trigger_action,
            )

    def set(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def acknowledge(self, acknowledged_by: str) -> dict:
        """Apply acknowledgement: set cooldown, clear override, reset alert state.

        Returns a snapshot of the state at the moment of acknowledgement
        (used for logging and Telegram confirmation).
        """
        with self._lock:
            snap = dict(
                bg=self.bg,
                trend=self.trend,
                action=self.override_action or self.active_dose or "none",
                override_was_active=self.override_action is not None,
            )
            self.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=900)
            self.cooldown_trigger_action = self.override_action or self.active_dose
            self.override_action = None
            self.alert_pending = False
            logger.info(
                "STATE: acknowledged by '%s' - cooldown until %s",
                acknowledged_by, self.cooldown_until.isoformat(),
            )
            return snap


# ---------------------------------------------------------------------------
# Polling logic
# ---------------------------------------------------------------------------

async def _poll_once(state: AppState) -> None:
    """Fetch Nightscout data and update state + alerts."""
    result = nightscout.fetch_latest_entry()
    if result is None:
        # Keep last known state - errors already logged in nightscout.py
        return

    bg, direction = result
    chart_action = chart.get_action(bg, direction)
    now = datetime.now(timezone.utc)

    with state._lock:
        state.bg = bg
        state.trend = direction
        state.last_updated = now

        effective_action = state.override_action or chart_action
        state.active_dose = chart_action  # always track chart result separately

        if not effective_action:
            # No dose needed - clear alert state
            state.alert_pending = False
            return

        cooldown_active = state.cooldown_until is not None and now < state.cooldown_until

        if cooldown_active:
            if chart.is_worse_action(effective_action, state.cooldown_trigger_action or ""):
                # Situation has worsened - override cooldown and re-alert immediately
                logger.warning(
                    "STATE: action worsened during cooldown (%s -> %s) - re-alerting",
                    state.cooldown_trigger_action, effective_action,
                )
                state.cooldown_trigger_action = effective_action
                state.alert_pending = True
                state.last_alert_sent = now
                state.last_alerted_dose = effective_action
                should_alert = True
            else:
                should_alert = False
        else:
            # No cooldown - alert if we haven't already for this episode
            if not state.alert_pending:
                state.alert_pending = True
                state.last_alert_sent = now
                state.last_alerted_dose = effective_action
                should_alert = True
            else:
                should_alert = False

    if should_alert:
        await telegram_bot.send_alert(
            state.bot_app,
            action=effective_action,
            bg=bg,
            trend=direction,
            is_repeat=False,
        )


async def _maybe_repeat_alert(state: AppState) -> None:
    """Send a repeat alert if the dose has been pending for more than 10 minutes."""
    snap = state.get_snapshot()
    if not snap["alert_pending"]:
        return

    effective_action = snap["override_action"] or snap["active_dose"]
    if not effective_action:
        return

    now = datetime.now(timezone.utc)
    cooldown_active = snap["cooldown_until"] is not None and now < snap["cooldown_until"]
    if cooldown_active:
        return

    last_sent = snap["last_alert_sent"]
    if last_sent is None:
        return
    if (now - last_sent).total_seconds() < 600:  # 10 minutes
        return

    logger.info("STATE: sending repeat alert for action=%s", effective_action)
    state.set(last_alert_sent=now)  # update before sending to avoid double-fire on slow send
    await telegram_bot.send_alert(
        state.bot_app,
        action=effective_action,
        bg=snap["bg"],
        trend=snap["trend"],
        is_repeat=True,
    )


async def nightscout_poll_loop(state: AppState) -> None:
    """Runs forever, polling Nightscout every 5 minutes."""
    logger.info("POLL: starting Nightscout poll loop (interval=300s)")
    while True:
        try:
            await _poll_once(state)
        except Exception as exc:
            logger.error("POLL: uncaught error in poll_once: %s", exc)
        await asyncio.sleep(300)


async def repeat_alert_loop(state: AppState) -> None:
    """Runs forever, checking every 60 seconds if a repeat alert is due."""
    logger.info("REPEAT-ALERT: watchdog started (interval=60s)")
    while True:
        await asyncio.sleep(60)
        try:
            await _maybe_repeat_alert(state)
        except Exception as exc:
            logger.error("REPEAT-ALERT: uncaught error: %s", exc)


# ---------------------------------------------------------------------------
# Flask thread
# ---------------------------------------------------------------------------

def _run_flask(state: AppState) -> None:
    flask_api.set_state(state)
    logger.info("FLASK: starting on port %d", config.API_PORT)
    flask_api.app.run(host="0.0.0.0", port=config.API_PORT, use_reloader=False)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def async_main() -> None:
    state = AppState()

    # Wire Flask state before starting Flask thread
    flask_thread = threading.Thread(target=_run_flask, args=(state,), daemon=True)
    flask_thread.start()

    # Start Telegram bot
    bot_app = await telegram_bot.start(state)
    state.bot_app = bot_app
    state.event_loop = asyncio.get_running_loop()

    # Launch background tasks
    poll_task = asyncio.create_task(nightscout_poll_loop(state))
    repeat_task = asyncio.create_task(repeat_alert_loop(state))

    logger.info("MAIN: all components running")

    # Wait until cancelled (e.g. SIGINT/SIGTERM)
    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("MAIN: shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    await stop_event.wait()

    logger.info("MAIN: shutting down")
    poll_task.cancel()
    repeat_task.cancel()
    await asyncio.gather(poll_task, repeat_task, return_exceptions=True)
    await telegram_bot.stop(bot_app)


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("MAIN: exiting")


if __name__ == "__main__":
    main()
