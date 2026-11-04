from datetime import datetime, time, timedelta

# This is for mapping weekday() to the opening window, Sunday (6) is missing on purpose
OPENING_WINDOWS: dict[int, tuple[time, time]] = {
    **{weekday: (time(9), time(18)) for weekday in range(5)},
    5: (time(9), time(13)),
}

WEEKDAY_NAMES_PT = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


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

    def find_next_opening(self, moment: datetime) -> datetime:
        """Finds when the store opens next, used to tell customers when someone will answer.

        Args:
            moment: Date and time in the store's time zone.

        Returns:
            The next opening moment after ``moment``. If the store is open, the next one
            after today's closing.
        """
        for days_ahead in range(8):
            day = moment + timedelta(days=days_ahead)
            window = OPENING_WINDOWS.get(day.weekday())
            if window is None:
                continue
            opening = day.replace(hour=window[0].hour, minute=0, second=0, microsecond=0)
            if opening > moment:
                return opening
        raise RuntimeError("OPENING_WINDOWS has no opening day")

    def describe_next_opening(self, moment: datetime) -> str:
        """Writes the next opening in Portuguese, e.g. "segunda às 09:00".

        Args:
            moment: Date and time in the store's time zone.

        Returns:
            "hoje às ...", "amanhã às ..." or the weekday name with the time.
        """
        opening = self.find_next_opening(moment)
        days_ahead = (opening.date() - moment.date()).days
        if days_ahead == 0:
            day_name = "hoje"
        elif days_ahead == 1:
            day_name = "amanhã"
        else:
            day_name = WEEKDAY_NAMES_PT[opening.weekday()]
        return f"{day_name} às {opening:%H:%M}"
