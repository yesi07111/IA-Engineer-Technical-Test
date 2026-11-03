from datetime import datetime, time

# This is for mapping weekday() to the opening window, Sunday (6) is missing on purpose
OPENING_WINDOWS: dict[int, tuple[time, time]] = {
    **{weekday: (time(9), time(18)) for weekday in range(5)},
    5: (time(9), time(13)),
}


class StoreSchedule:
    """Opening hours of the physical store and the WhatsApp service (policy section 2)."""

    def is_open_at(self, moment: datetime) -> bool:
        """Checks if the store is open at a given moment.

        Args:
            moment: Date and time in the store's time zone.

        Returns:
            True during opening hours. Holidays are not modelled, so they count as normal days.
        """
        window = OPENING_WINDOWS.get(moment.weekday())
        return window is not None and window[0] <= moment.time() < window[1]

    def describe_hours(self) -> str:
        """Writes the weekly schedule in Portuguese.

        Returns:
            A one line summary of the opening hours.
        """
        return "Segunda a sexta 09:00–18:00 · Sábado 09:00–13:00 · Domingos e feriados: fechado"
