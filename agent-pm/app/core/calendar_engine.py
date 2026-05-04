"""
Calendar engine for the Construction Planning Agent.

Handles working-day arithmetic for Australian construction contexts (§12):
- 5, 5.5, or 6-day working weeks
- State public holidays where available
- Industry RDO rosters (CFMEU EBA)
- Christmas/New Year shutdown (21 Dec – 14 Jan)
- Weather-day allowances
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Optional

from dateutil.rrule import rrule, WEEKLY, MO, TU, WE, TH, FR, SA


# ── Calendar definition ───────────────────────────────────────────────────────

class WorkingCalendar:
    """A construction working calendar with holidays, RDOs, and shutdowns."""

    def __init__(
        self,
        calendar_id: str = "VIC_5DAY_STANDARD_2026",
        work_days: Optional[list[int]] = None,
        holidays: Optional[list[datetime.date]] = None,
        rdo_dates: Optional[list[datetime.date]] = None,
        shutdown_start: Optional[datetime.date] = None,
        shutdown_end: Optional[datetime.date] = None,
        weather_buffer_pct: float = 0.0,
    ):
        self.calendar_id = calendar_id
        # Default: Monday–Friday (0=Mon, 4=Fri)
        self.work_days = work_days or [0, 1, 2, 3, 4]
        self.holidays = set(holidays or [])
        self.rdo_dates = set(rdo_dates or [])
        self.shutdown_start = shutdown_start
        self.shutdown_end = shutdown_end
        self.weather_buffer_pct = weather_buffer_pct

        # Pre-compute shutdown dates
        self._shutdown_dates: set[datetime.date] = set()
        if shutdown_start and shutdown_end:
            d = shutdown_start
            while d <= shutdown_end:
                self._shutdown_dates.add(d)
                d += datetime.timedelta(days=1)

    def is_working_day(self, date: datetime.date) -> bool:
        """Check if a date is a working day."""
        if date.weekday() not in self.work_days:
            return False
        if self.shutdown_start and self.shutdown_end:
            # Treat the Christmas/New Year shutdown as an annual construction
            # shutdown, not a one-off 2026/27 period.
            if (date.month == 12 and date.day >= self.shutdown_start.day) or (
                date.month == 1 and date.day <= self.shutdown_end.day
            ):
                return False
        if date in self.holidays:
            return False
        if date in self.rdo_dates:
            return False
        if date in self._shutdown_dates:
            return False
        return True

    def add_working_days(self, start: datetime.date, days: int) -> datetime.date:
        """
        Add a number of working days to a start date.
        Returns the end date (inclusive of the last working day).
        If days <= 0, returns the start date.
        """
        if days <= 0:
            return start

        current = start
        remaining = days

        # If start is not a working day, advance to the first working day
        while not self.is_working_day(current):
            current += datetime.timedelta(days=1)

        # The start day counts as day 1
        remaining -= 1

        while remaining > 0:
            current += datetime.timedelta(days=1)
            if self.is_working_day(current):
                remaining -= 1

        return current

    def working_days_between(
        self, start: datetime.date, end: datetime.date
    ) -> int:
        """Count working days between two dates (inclusive of both)."""
        if end < start:
            return 0
        count = 0
        current = start
        while current <= end:
            if self.is_working_day(current):
                count += 1
            current += datetime.timedelta(days=1)
        return count

    def next_working_day(self, date: datetime.date) -> datetime.date:
        """Return the next working day on or after the given date."""
        current = date
        while not self.is_working_day(current):
            current += datetime.timedelta(days=1)
        return current

    def previous_working_day(self, date: datetime.date) -> datetime.date:
        """Return the previous working day on or before the given date."""
        current = date
        while not self.is_working_day(current):
            current -= datetime.timedelta(days=1)
        return current

    def add_working_days_exclusive(self, start: datetime.date, days: int) -> datetime.date:
        """
        Move by working days excluding the start date.

        A +1 shift returns the next working day after start; a -1 shift returns
        the previous working day before start. This is the correct operation for
        CPM relationship gaps such as FS+0, where the successor starts on the
        next working day after predecessor finish.
        """
        current = start
        remaining = abs(days)
        step = 1 if days >= 0 else -1
        while remaining > 0:
            current += datetime.timedelta(days=step)
            if self.is_working_day(current):
                remaining -= 1
        return current

    def subtract_working_days_inclusive(
        self,
        finish: datetime.date,
        duration_days: int,
    ) -> datetime.date:
        """
        Calculate an activity start from an inclusive finish date and duration.

        A one-day activity that finishes on Tuesday starts on Tuesday; a two-day
        activity starts on the previous working day.
        """
        current = self.previous_working_day(finish)
        remaining = max(0, duration_days - 1)
        while remaining > 0:
            current = self.add_working_days_exclusive(current, -1)
            remaining -= 1
        return current

    def working_days_between_exclusive(
        self,
        start: datetime.date,
        end: datetime.date,
    ) -> int:
        """Count working days after start up to and including end."""
        if end <= start:
            return 0
        count = 0
        current = start
        while current < end:
            current += datetime.timedelta(days=1)
            if self.is_working_day(current):
                count += 1
        return count

    def apply_weather_buffer(self, duration_days: int) -> int:
        """Apply weather buffer percentage to a duration."""
        if self.weather_buffer_pct > 0:
            buffer = max(1, round(duration_days * self.weather_buffer_pct))
            return duration_days + buffer
        return duration_days


# ── Victorian calendar factory ─────────────────────────────────────────────────

def get_vic_public_holidays_2026() -> list[datetime.date]:
    """Victorian public holidays for 2026 (11 + AFL Grand Final eve)."""
    return [
        datetime.date(2026, 1, 1),   # New Year's Day
        datetime.date(2026, 1, 26),  # Australia Day
        datetime.date(2026, 3, 9),   # Labour Day (VIC)
        datetime.date(2026, 4, 3),   # Good Friday
        datetime.date(2026, 4, 4),   # Saturday before Easter Sunday
        datetime.date(2026, 4, 6),   # Easter Monday
        datetime.date(2026, 4, 25),  # ANZAC Day
        datetime.date(2026, 6, 8),   # Queen's Birthday (VIC)
        datetime.date(2026, 9, 25),  # AFL Grand Final Friday (estimate)
        datetime.date(2026, 11, 3),  # Melbourne Cup Day
        datetime.date(2026, 12, 25), # Christmas Day
        datetime.date(2026, 12, 26), # Boxing Day (substitute if needed)
        datetime.date(2026, 12, 28), # Boxing Day substitute
    ]


def get_vic_public_holidays_2027() -> list[datetime.date]:
    """Victorian public holidays for 2027."""
    return [
        datetime.date(2027, 1, 1),   # New Year's Day
        datetime.date(2027, 1, 26),  # Australia Day
        datetime.date(2027, 3, 8),   # Labour Day (VIC)
        datetime.date(2027, 3, 26),  # Good Friday
        datetime.date(2027, 3, 27),  # Saturday before Easter Sunday
        datetime.date(2027, 3, 29),  # Easter Monday
        datetime.date(2027, 4, 25),  # ANZAC Day (Sunday → Monday substitute)
        datetime.date(2027, 6, 14),  # Queen's Birthday (VIC)
        datetime.date(2027, 9, 24),  # AFL Grand Final Friday (estimate)
        datetime.date(2027, 11, 2),  # Melbourne Cup Day
        datetime.date(2027, 12, 25), # Christmas Day
        datetime.date(2027, 12, 27), # Boxing Day (substitute)
    ]


def generate_rdo_dates_2026() -> list[datetime.date]:
    """
    Generate approximate RDO dates for 2026 (every 20th working day).
    Based on CFMEU EBA pattern for Victorian commercial construction.
    """
    rdos = []
    start = datetime.date(2026, 1, 5)
    end = datetime.date(2026, 12, 31)
    working_day_count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            working_day_count += 1
            if working_day_count % 20 == 0:
                rdos.append(current)
        current += datetime.timedelta(days=1)
    return rdos


def create_standard_calendar(
    calendar_id: str = "VIC_5DAY_STANDARD_2026",
    include_rdos: bool = False,
    weather_buffer_pct: float = 0.0,
    work_days: Optional[list[int]] = None,
) -> WorkingCalendar:
    """Create a standard Victorian working calendar."""
    holidays = get_vic_public_holidays_2026() + get_vic_public_holidays_2027()
    rdos = generate_rdo_dates_2026() if include_rdos else []

    return WorkingCalendar(
        calendar_id=calendar_id,
        work_days=work_days or [0, 1, 2, 3, 4],
        holidays=holidays,
        rdo_dates=rdos,
        shutdown_start=datetime.date(2026, 12, 21),
        shutdown_end=datetime.date(2027, 1, 14),
        weather_buffer_pct=weather_buffer_pct,
    )


def load_calendar_from_library(calendar_id: str) -> WorkingCalendar:
    """Load a calendar definition from the JSON library, fall back to defaults."""
    lib_path = Path(__file__).parent.parent / "libraries" / "calendars.json"
    if lib_path.exists():
        with open(lib_path) as f:
            data = json.load(f)
        if calendar_id in data:
            cal_data = data[calendar_id]
            holidays = [
                datetime.date.fromisoformat(d)
                for d in cal_data.get("holidays", [])
            ]
            rdos = [
                datetime.date.fromisoformat(d)
                for d in cal_data.get("rdo_dates", [])
            ]
            shutdown_start = (
                datetime.date.fromisoformat(cal_data["shutdown_start"])
                if cal_data.get("shutdown_start")
                else None
            )
            shutdown_end = (
                datetime.date.fromisoformat(cal_data["shutdown_end"])
                if cal_data.get("shutdown_end")
                else None
            )
            return WorkingCalendar(
                calendar_id=calendar_id,
                work_days=cal_data.get("work_days", [0, 1, 2, 3, 4]),
                holidays=holidays,
                rdo_dates=rdos,
                shutdown_start=shutdown_start,
                shutdown_end=shutdown_end,
                weather_buffer_pct=cal_data.get("weather_buffer_pct", 0.0),
            )

    # Fall back to standard calendar
    return create_standard_calendar(calendar_id)


# ── Calendar registry ──────────────────────────────────────────────────────────

CALENDAR_OPTIONS = {
    "VIC_5DAY_STANDARD_2026": "Mon-Fri, VIC holidays, Christmas shutdown",
    "VIC_5.5DAY_2026": "Mon-Fri + Sat AM, VIC holidays, Christmas shutdown",
    "VIC_6DAY_2026": "Mon-Sat, VIC holidays, Christmas shutdown",
    "VIC_5DAY_RDO_2026": "Mon-Fri, VIC holidays, CFMEU RDOs, Christmas shutdown",
    "SA_5DAY_STANDARD_2026": "Mon-Fri, SA holidays, Christmas shutdown",
    "SA_6DAY_2026": "Mon-Sat, SA holidays, Christmas shutdown",
}


def get_available_calendars() -> dict[str, str]:
    """Return available calendar options."""
    return CALENDAR_OPTIONS


def default_calendar_for_location(location: str | None) -> str:
    """Choose the best available default calendar for a project location."""
    text = (location or "").lower()
    if any(term in text for term in ["adelaide", "south australia", " sa", "sa "]):
        return "SA_5DAY_STANDARD_2026"
    return "VIC_5DAY_STANDARD_2026"
