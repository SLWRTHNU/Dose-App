# Dose-App Backend

Python 3.11+ backend. Polls Nightscout every 5 minutes, runs the BG/trend action chart, sends Telegram alerts, exposes a REST API for the watch app, and logs acknowledgements to Google Sheets.

---

## Environment Variables

Create `/etc/dose-app/env` (referenced by the systemd unit) with the following:

```
NIGHTSCOUT_URL=https://your-nightscout-instance.herokuapp.com
NIGHTSCOUT_TOKEN=your_nightscout_token

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_GROUP_ID=-100xxxxxxxxx
TELEGRAM_PARENT_IDS=111111111,222222222

GOOGLE_CREDENTIALS_JSON=/etc/dose-app/google-credentials.json
GOOGLE_SHEET_NAME=DoseApp Log

API_PORT=5000
```

---

## Telegram Setup

### 1. Create a bot via BotFather

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts.
3. BotFather gives you a token like `123456789:ABCdef...` - this is `TELEGRAM_BOT_TOKEN`.

### 2. Get the group chat ID

1. Add the bot to your family group chat.
2. Send any message in the group.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser.
4. Find the `chat.id` field in the response - it will be a negative number like `-100123456789`.
5. Set `TELEGRAM_GROUP_ID` to this value.

### 3. Get parent chat IDs

1. Start a private chat with the bot (search for its username).
2. Send `/help`.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` and find your `message.chat.id` (positive number).
4. Repeat for each parent. Set `TELEGRAM_PARENT_IDS` to a comma-separated list.

---

## Google Sheets Setup

### 1. Create a Google Cloud service account

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or use an existing one).
3. Enable the **Google Sheets API** for the project.
4. Go to **IAM & Admin > Service Accounts** and click **Create Service Account**.
5. Give it a name (e.g. `dose-app-sheets`), click **Done**.

### 2. Download credentials JSON

1. Click the service account you just created.
2. Go to the **Keys** tab.
3. Click **Add Key > Create new key**, choose **JSON**, and download the file.
4. Copy it to `/etc/dose-app/google-credentials.json` on the server.
5. Set `GOOGLE_CREDENTIALS_JSON=/etc/dose-app/google-credentials.json`.

### 3. Share the sheet with the service account

1. Create a Google Sheet named exactly as set in `GOOGLE_SHEET_NAME` (default: `DoseApp Log`).
2. Add a header row: `timestamp | bg_at_time | trend_at_time | action_given | acknowledged_by | override_was_active`
3. Open the sheet, click **Share**, and share it (Editor access) with the service account email (ends in `@<project>.iam.gserviceaccount.com`).

---

## Deployment

### Install

```bash
sudo apt install python3.11 python3.11-venv
sudo mkdir -p /opt/dose-app /etc/dose-app
sudo cp -r backend /opt/dose-app/backend
cd /opt/dose-app
python3.11 -m venv venv
venv/bin/pip install -r backend/requirements.txt
```

### Configure

```bash
sudo cp backend/dose-app.service /etc/systemd/system/
sudo nano /etc/dose-app/env         # fill in env vars
sudo cp /path/to/credentials.json /etc/dose-app/google-credentials.json
sudo chmod 600 /etc/dose-app/env /etc/dose-app/google-credentials.json
```

### Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable dose-app
sudo systemctl start dose-app
sudo journalctl -u dose-app -f      # follow logs
```

---

## REST API

All endpoints are unauthenticated in the current build. Auth scaffolding is in `check_auth()` in `api.py`.

**GET /status**
```json
{
  "action": "jb:3",
  "bg": 5.4,
  "trend": "Flat",
  "trend_arrow": "-",
  "cooldown_active": false,
  "cooldown_until": null,
  "override_active": false,
  "last_updated": "2026-01-01T12:00:00+00:00"
}
```

**POST /acknowledge**
Body: `{ "acknowledged_by": "watch" }`
Response: `{ "ok": true }`

**POST /override**
Body: `{ "action": "jb:2" }` or `{ "action": "clear" }`
Response: `{ "ok": true }`
