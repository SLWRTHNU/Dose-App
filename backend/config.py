import os

NIGHTSCOUT_URL = os.environ.get("NIGHTSCOUT_URL", "https://sennaloop-673ad2782247.herokuapp.com")
NIGHTSCOUT_TOKEN = os.environ.get("NIGHTSCOUT_TOKEN", "")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "")
TELEGRAM_PARENT_IDS = [
    cid.strip()
    for cid in os.environ.get("TELEGRAM_PARENT_IDS", "").split(",")
    if cid.strip()
]

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "credentials.json")
GOOGLE_SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "DoseApp Log")

API_PORT = int(os.environ.get("API_PORT", "5000"))

TIMEZONE = os.environ.get("TIMEZONE", "America/Toronto")
