import re
import uuid
from typing import Any

from pydantic import ValidationError

from emporio_agent.domain.models import HandoffTicket, TicketReason
from emporio_agent.domain.text import keep_only_digits
from emporio_agent.errors import InvalidRequestError
from emporio_agent.ports.clock import Clock
from emporio_agent.ports.repositories import TicketRepository

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TEAM_RESPONSE_TIME = "até 24 horas úteis"


def looks_like_contact(contact: str) -> bool:
    """Checks that a text is a plausible e-mail or Brazilian phone number.

    Args:
        contact: What the customer gave as contact.

    Returns:
        True for an e-mail like "a@b.com" or a phone with 10 to 13 digits.
    """
    contact = contact.strip()
    if "@" in contact:
        return bool(EMAIL_PATTERN.match(contact))
    return 10 <= len(keep_only_digits(contact)) <= 13


class HandoffService:
    """Opens tickets so a person from the store team can continue a case."""

    def __init__(self, tickets: TicketRepository, clock: Clock) -> None:
        """Keeps where tickets are stored and the clock for their date.

        Args:
            tickets: Ticket storage.
            clock: Current time in the store's time zone.
        """
        self._tickets = tickets
        self._clock = clock

    def open_ticket(
        self,
        reason: TicketReason,
        summary: str,
        customer_contact: str,
        customer_name: str | None = None,
        order_id: int | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Creates a ticket for the team with everything needed to continue the case.

        Args:
            reason: Kind of case.
            summary: What happened and what the customer wants, written by the agent.
            customer_contact: E-mail or phone where the team can answer.
            customer_name: Name, when the customer gave it.
            order_id: Related order, if any.
            session_id: Conversation id, so the team can read the chat.

        Returns:
            The ticket number and when the customer can expect an answer.

        Raises:
            InvalidRequestError: If the contact is not an e-mail or phone, or the summary
                is too short or too long.
        """
        if not looks_like_contact(customer_contact):
            raise InvalidRequestError(
                "customer_contact must be a valid e-mail or phone, ask the customer for it."
            )
        now = self._clock.now()
        ticket_id = f"EM-{now:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        try:
            ticket = HandoffTicket(
                id=ticket_id,
                created_at=now,
                reason=reason,
                summary=summary.strip(),
                customer_contact=customer_contact.strip(),
                customer_name=customer_name.strip() if customer_name else None,
                order_id=order_id,
                session_id=session_id,
            )
        except ValidationError as error:
            raise InvalidRequestError(
                "The ticket summary must have between 10 and 1000 characters."
            ) from error
        self._tickets.save(ticket)
        return {"ticket_id": ticket.id, "team_response_time": TEAM_RESPONSE_TIME}

    def list_tickets(self) -> list[HandoffTicket]:
        """Lists the tickets for the team, newest first.

        Returns:
            Every stored ticket.
        """
        return sorted(self._tickets.list_all(), key=lambda ticket: ticket.created_at, reverse=True)
