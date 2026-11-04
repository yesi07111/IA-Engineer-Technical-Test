import threading
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from emporio_agent.domain.models import HandoffTicket
from emporio_agent.errors import DataLoadError
from emporio_agent.ports.repositories import TicketRepository


class JsonlTicketRepository(TicketRepository):
    """Tickets stored as one JSON object per line, easy to read or import elsewhere."""

    def __init__(self, path: Path) -> None:
        """Prepares the file, creating its folder if needed.

        Args:
            path: Location of the .jsonl file.
        """
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, ticket: HandoffTicket) -> None:
        """Appends a ticket to the file.

        Args:
            ticket: Ticket to store.
        """
        # This is for the web API, two requests could write at the same time
        with self._lock, self._path.open("a", encoding="utf-8") as file:
            file.write(ticket.model_dump_json() + "\n")

    def list_all(self) -> Sequence[HandoffTicket]:
        """Reads every ticket of the file.

        Returns:
            The tickets, oldest first. Empty when the file does not exist yet.

        Raises:
            DataLoadError: If a line is not a valid ticket.
        """
        if not self._path.is_file():
            return []
        tickets = []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                tickets.append(HandoffTicket.model_validate_json(line))
            except ValidationError as error:
                raise DataLoadError(f"{self._path.name}, line {line_number}: {error}") from error
        return tickets
