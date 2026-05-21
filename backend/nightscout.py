import logging
from typing import Optional, Tuple

import requests

import config

logger = logging.getLogger(__name__)


def fetch_latest_entry() -> Optional[Tuple[float, str]]:
    """Fetch the latest BG entry from Nightscout.

    Returns (bg_mmol, direction) on success, or None on any failure.
    Failures are logged loudly - this is a medical tool.
    """
    url = f"{config.NIGHTSCOUT_URL}/api/v1/entries.json"
    params = {"count": 1, "token": config.NIGHTSCOUT_TOKEN}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("NIGHTSCOUT: fetch failed (network/HTTP error): %s", exc)
        return None
    except ValueError as exc:
        logger.error("NIGHTSCOUT: response is not valid JSON: %s", exc)
        return None

    if not data:
        logger.error("NIGHTSCOUT: API returned an empty entries list")
        return None

    entry = data[0]
    sgv = entry.get("sgv")
    direction = entry.get("direction", "Flat")

    if sgv is None:
        logger.error("NIGHTSCOUT: entry is missing 'sgv' field: %s", entry)
        return None

    try:
        bg_mmol = round(float(sgv) / 18.0, 1)
    except (TypeError, ValueError) as exc:
        logger.error("NIGHTSCOUT: cannot convert sgv=%r to float: %s", sgv, exc)
        return None

    logger.info("NIGHTSCOUT: bg=%.1f mmol/L  direction=%s  raw_sgv=%s", bg_mmol, direction, sgv)
    return bg_mmol, direction
