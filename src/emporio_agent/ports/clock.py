from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Gives the current moment in the store's time zone.

    It is an interface so tests can freeze time and check hours and deadlines.
    """

    @abstractmethod
    def now(self) -> datetime:
        """Gets the current date and time.

        Returns:
            A timezone aware datetime in the store's time zone.
        """
