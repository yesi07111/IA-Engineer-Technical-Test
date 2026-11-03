from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.domain.store_hours import StoreSchedule
from emporio_agent.errors import ConfigurationError
from emporio_agent.infrastructure.system_clock import SystemClock

CAMPO_GRANDE = ZoneInfo("America/Campo_Grande")


def at(year, month, day, hour, minute=0):
    """Builds a moment in Campo Grande time.

    Args:
        year: Year.
        month: Month.
        day: Day.
        hour: Hour.
        minute: Minute.

    Returns:
        A timezone aware datetime.
    """
    return datetime(year, month, day, hour, minute, tzinfo=CAMPO_GRANDE)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (at(2026, 11, 3, 8, 59), False),  # Tuesday before opening
        (at(2026, 11, 3, 9, 0), True),
        (at(2026, 11, 3, 17, 59), True),
        (at(2026, 11, 3, 18, 0), False),
        (at(2026, 11, 7, 12, 59), True),  # Saturday
        (at(2026, 11, 7, 13, 0), False),
        (at(2026, 11, 8, 10, 0), False),  # Sunday
    ],
)
def test_opening_hours(moment, expected):
    assert StoreSchedule().is_open_at(moment) is expected


def test_system_clock_uses_the_store_time_zone():
    assert SystemClock("America/Campo_Grande").now().utcoffset().total_seconds() == -4 * 3600


def test_unknown_time_zone_is_a_configuration_error():
    with pytest.raises(ConfigurationError):
        SystemClock("Mars/Olympus_Mons")


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (at(2026, 11, 3, 7, 30), "hoje às 09:00"),  # Tuesday early morning
        (at(2026, 11, 3, 19, 0), "amanhã às 09:00"),
        (at(2026, 11, 7, 14, 0), "segunda às 09:00"),  # Saturday afternoon
        (at(2026, 11, 8, 10, 0), "amanhã às 09:00"),  # Sunday
    ],
)
def test_next_opening_is_described_in_portuguese(moment, expected):
    assert StoreSchedule().describe_next_opening(moment) == expected
