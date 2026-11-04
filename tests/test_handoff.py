from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.application.handoff import HandoffService, looks_like_contact
from emporio_agent.domain.models import TicketReason
from emporio_agent.errors import DataLoadError, InvalidRequestError
from emporio_agent.infrastructure.jsonl_tickets import JsonlTicketRepository
from tests.test_tools import FrozenClock

NOW = datetime(2026, 11, 3, 10, 30, tzinfo=ZoneInfo("America/Campo_Grande"))


@pytest.fixture
def handoff(tmp_path):
    return HandoffService(JsonlTicketRepository(tmp_path / "tickets.jsonl"), FrozenClock(NOW))


@pytest.mark.parametrize(
    ("contact", "expected"),
    [
        ("pedro.oliveira@jmail.com", True),
        ("(67) 98432-1098", True),
        ("+55 67 98432-1098", True),
        ("pedro@", False),
        ("1234", False),
        ("me liga", False),
    ],
)
def test_contact_validation(contact, expected):
    assert looks_like_contact(contact) is expected


def test_ticket_is_saved_and_listed(handoff):
    answer = handoff.open_ticket(
        TicketReason.LATE_DELIVERY,
        "Pedido 8 enviado com entrega prevista vencida, cliente quer previsão.",
        "anacarol.ferreira@coldmail.com",
        customer_name="Ana",
        order_id=8,
        session_id="abc123",
    )

    assert answer["ticket_id"].startswith("EM-20261103-")
    assert "24 horas úteis" in answer["team_response_time"]
    [ticket] = handoff.list_tickets()
    assert ticket.id == answer["ticket_id"]
    assert ticket.order_id == 8
    assert ticket.session_id == "abc123"


def test_tickets_survive_a_restart(tmp_path):
    path = tmp_path / "tickets.jsonl"
    HandoffService(JsonlTicketRepository(path), FrozenClock(NOW)).open_ticket(
        TicketReason.COMPLAINT, "Cliente reclamou do atendimento.", "a@b.com"
    )

    reopened = HandoffService(JsonlTicketRepository(path), FrozenClock(NOW))

    assert len(reopened.list_tickets()) == 1


def test_invalid_contact_is_rejected(handoff):
    with pytest.raises(InvalidRequestError, match="e-mail or phone"):
        handoff.open_ticket(TicketReason.OTHER, "Cliente quer falar com alguém.", "amanhã")


def test_short_summary_is_rejected(handoff):
    with pytest.raises(InvalidRequestError, match="summary"):
        handoff.open_ticket(TicketReason.OTHER, "oi", "a@b.com")


def test_corrupted_ticket_file_is_reported(tmp_path):
    path = tmp_path / "tickets.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(DataLoadError, match="line 1"):
        JsonlTicketRepository(path).list_all()


def test_no_file_means_no_tickets(tmp_path):
    assert JsonlTicketRepository(tmp_path / "missing" / "tickets.jsonl").list_all() == []
