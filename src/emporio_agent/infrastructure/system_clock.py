from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from emporio_agent.errors import ConfigurationError
from emporio_agent.ports.clock import Clock


class SystemClock(Clock):
    """Real clock of the machine, converted to the store's time zone."""

    def __init__(self, timezone_name: str = "America/Campo_Grande") -> None:
        """Prepares the clock for a time zone.

        Args:
            timezone_name: IANA name of the time zone.

        Raises:
            ConfigurationError: If the time zone name is unknown.
        """
        try:
            self._zone = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ConfigurationError(f"Unknown time zone: {timezone_name}") from error

    def now(self) -> datetime:
        """Gets the current date and time.

        Returns:
            The current moment in the configured time zone.
        """
        return datetime.now(self._zone)
