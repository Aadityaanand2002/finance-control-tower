"""Timezone helpers for API timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ist_now() -> datetime:
    return datetime.now(IST)


def ensure_aware_utc(dt: datetime) -> datetime:
    """SQLite often returns naive datetimes; treat those as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso_z(dt: datetime | None) -> str | None:
    """Serialize for API as India local time with explicit offset.

    Demo merchants expect wall-clock IST on exceptions / activity, not UTC hour.
    """
    if dt is None:
        return None
    local = ensure_aware_utc(dt).astimezone(IST)
    return local.isoformat(timespec="milliseconds")
