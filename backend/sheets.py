import logging
from datetime import datetime, timezone
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = [
    "timestamp",
    "bg_at_time",
    "trend_at_time",
    "action_given",
    "acknowledged_by",
    "override_was_active",
]

_sheet: Optional[gspread.Worksheet] = None


def _get_sheet() -> Optional[gspread.Worksheet]:
    global _sheet
    if _sheet is not None:
        return _sheet
    try:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_JSON, scopes=SCOPES
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open(config.GOOGLE_SHEET_NAME)
        _sheet = spreadsheet.sheet1
        logger.info("SHEETS: connected to '%s'", config.GOOGLE_SHEET_NAME)
        return _sheet
    except FileNotFoundError:
        logger.error(
            "SHEETS: credentials file not found at '%s'", config.GOOGLE_CREDENTIALS_JSON
        )
        return None
    except Exception as exc:
        logger.error("SHEETS: init failed: %s", exc)
        return None


def log_acknowledgement(
    bg: float,
    trend: str,
    action: str,
    acknowledged_by: str,
    override_was_active: bool,
) -> None:
    """Append one row to the log sheet. Logs errors but does not raise."""
    sheet = _get_sheet()
    if sheet is None:
        logger.error(
            "SHEETS: cannot log acknowledgement - sheet unavailable. "
            "Data would have been: bg=%s trend=%s action=%s by=%s override=%s",
            bg, trend, action, acknowledged_by, override_was_active,
        )
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    row = [timestamp, bg, trend, action, acknowledged_by, str(override_was_active)]
    try:
        sheet.append_row(row, value_input_option="RAW")
        logger.info("SHEETS: logged: %s", row)
    except Exception as exc:
        logger.error("SHEETS: append_row failed: %s | attempted row: %s", exc, row)
