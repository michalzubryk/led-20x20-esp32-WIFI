"""Daily lighting window, evaluated in a named time zone (including DST)."""
from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_SCHEDULE = dict(enabled=False, on="16:00", off="23:00", timezone="Europe/Warsaw")


def validate_schedule(data, previous=None):
    if not isinstance(data, dict) or set(data) - set(DEFAULT_SCHEDULE):
        raise ValueError("Nieznane ustawienia harmonogramu")
    result = {**DEFAULT_SCHEDULE, **(previous or {}), **data}
    if type(result["enabled"]) is not bool:
        raise ValueError("Harmonogram: enabled musi być wartością logiczną")
    for key in ("on", "off"):
        if not isinstance(result[key], str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", result[key]):
            raise ValueError("Godzina musi mieć format HH:MM (00:00–23:59)")
    if result["on"] == result["off"]:
        raise ValueError("Godziny włączenia i wyłączenia muszą być różne")
    zone = result["timezone"]
    if not isinstance(zone, str) or not 1 <= len(zone) <= 80:
        raise ValueError("Niepoprawna strefa czasowa")
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Nieznana strefa czasowa, np. Europe/Warsaw") from None
    return result


def schedule_status(config, now=None):
    now = now if now is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("An aware datetime is required")
    local = now.astimezone(ZoneInfo(config["timezone"]))
    minute = local.strftime("%H:%M")
    start, end = config["on"], config["off"]
    in_window = start <= minute < end if start < end else minute >= start or minute < end
    return {**config, "active": not config["enabled"] or in_window,
            "localTime": local.isoformat(timespec="seconds")}
