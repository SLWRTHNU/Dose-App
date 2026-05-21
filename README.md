# Dose-App

Blood glucose management tool for a Type 1 diabetic child. Polls Nightscout, evaluates BG and trend against an action table, and alerts a family Telegram group with the recommended dose. A companion Apple Watch app lets any family member acknowledge the dose in seconds.

**Reliability is the top priority.** Failures are logged loudly. Nothing is silently swallowed.

---

## Components

| Directory | What it does |
|-----------|-------------|
| `backend/` | Python 3.11+ service - polls Nightscout, runs action chart, drives Telegram bot, exposes REST API |
| `watchapp/` | SwiftUI watchOS 9+ app - polls backend every 60 s, shows dose, lets you acknowledge with one tap |
| `.github/workflows/` | GitHub Actions CI - builds, signs, and archives the watchOS app on every push to main |

---

## How it works

1. **Nightscout poll** (every 5 min): fetch latest BG and trend direction.
2. **Chart lookup**: classify BG range and trend, look up required action (jellybeans, water, juice box, or nothing).
3. **State machine**:
   - If an action is required and no cooldown is active, send a Telegram group alert.
   - If the alert is not acknowledged within 10 minutes, send a repeat.
   - On acknowledgement (via watch tap or Telegram button): start a 15-minute cooldown.
   - If BG worsens during cooldown, override cooldown and re-alert immediately.
4. **Override**: parents can set a manual action via Telegram commands, which takes priority over the chart.

---

## Quick start

### Backend

```bash
cd backend
python3.11 -m venv venv
venv/bin/pip install -r requirements.txt
# copy and fill in environment variables
nano /etc/dose-app/env
venv/bin/python main.py
```

See `backend/README.md` for full deployment, Telegram, and Google Sheets setup.

### Watch App

Open `watchapp/DoseApp.xcodeproj` in Xcode. Set the backend IP in `DoseViewModel.swift` (the `backendURL` constant at the top of the file). Build and run on a paired Apple Watch.

For CI builds and sideloading, see `SETUP.md`.

---

## Action table summary

BG in mmol/L. Actions: `jb:N` = N jellybeans, `water`, `juicebox`.

| Trend | very low (&lt;=4.0) | low (4.1-4.8) | target (4.9-7.0) | high (8-10) | very high (11-13) | critical (13.1+) |
|-------|-------------|---------------|------------------|-------------|-------------------|------------------|
| Rising rapidly (DoubleUp) | - | - | - | - | water | water |
| Rising (SingleUp) | jb:2 | - | - | - | water | water |
| Slow rise (FortyFiveUp) | jb:2 | - | - | - | water | water |
| Stable (Flat) | jb:3 | jb:2 | - | - | - | - |
| Slow fall (FortyFiveDown) | jb:4 | jb:2 | - | - | - | - |
| Falling (SingleDown) | juicebox | jb:4 | jb:2 | - | - | - |
| Falling rapidly (DoubleDown) | juicebox | jb:5 | jb:3 | - | - | - |

---

## Environment variables

See `backend/README.md` for the full list with descriptions.

---

## License

Private - not for public distribution.
