from __future__ import annotations

from datetime import datetime, timedelta

from common import MAX_SCHEDULE_DAYS, TASHKENT, UTC


def parse_schedule_time(text: str) -> datetime:
    value = " ".join(text.strip().split())
    now = datetime.now(TASHKENT)

    parsed: datetime | None = None
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%y %H:%M"):
        try:
            parsed = datetime.strptime(value, fmt).replace(tzinfo=TASHKENT)
            break
        except ValueError:
            pass

    if parsed is None:
        try:
            partial = datetime.strptime(value, "%d.%m %H:%M")
            parsed = partial.replace(year=now.year, tzinfo=TASHKENT)
            if parsed <= now:
                parsed = parsed.replace(year=now.year + 1)
        except ValueError as exc:
            raise ValueError("format") from exc

    if parsed <= now:
        raise ValueError("past")
    if parsed > now + timedelta(days=MAX_SCHEDULE_DAYS):
        raise ValueError("too_far")
    return parsed.astimezone(UTC)


def local_label(value: datetime) -> str:
    return value.astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M")
