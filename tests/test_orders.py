from datetime import date

import pytest

from emporio_agent.application.orders import OrderLookupService, contact_matches_customer
from emporio_agent.domain.models import Customer
from emporio_agent.domain.returns import ReturnPolicy, ReturnReason
from emporio_agent.errors import InvalidRequestError

TODAY = date(2026, 11, 3)
PEDRO = Customer(
    id=3,
    name="Pedro Henrique Oliveira",
    phone="(67) 98432-1098",
    email="pedro.oliveira@jmail.com",
    city="Campo Grande",
)


@pytest.fixture
def order_lookup(orders, customers, products):
    return OrderLookupService(orders, customers, products, ReturnPolicy())


@pytest.mark.parametrize(
    "contact",
    [
        "pedro.oliveira@jmail.com",
        "  PEDRO.Oliveira@JMAIL.com ",
        "(67) 98432-1098",
        "67984321098",
        "+55 67 98432-1098",
        "98432-1098",
    ],
)
def test_contact_in_any_format_is_accepted(contact):
    assert contact_matches_customer(contact, PEDRO)


@pytest.mark.parametrize(
    "contact", ["pedro@jmail.com", "(67) 99999-9999", "1098", "pedro.oliveira"]
)
def test_wrong_contact_is_refused(contact):
    assert not contact_matches_customer(contact, PEDRO)


def test_owner_sees_the_order(order_lookup):
    summary = order_lookup.describe_order_status(1, "pedro.oliveira@jmail.com", TODAY)

    assert summary["status"] == "entregue"
    assert summary["tracking_code"] == "BRAB1234567BR"
    assert summary["items"] == ["1x Martin D-28 Dreadnought Natural"]
    assert summary["total"] == "R$ 11.499,00"
    assert summary["customer_first_name"] == "Pedro"


def test_wrong_owner_and_missing_order_look_the_same(order_lookup):
    wrong_owner = order_lookup.describe_order_status(1, "ana@jmail.com", TODAY)
    missing = order_lookup.describe_order_status(999, "pedro.oliveira@jmail.com", TODAY)

    assert wrong_owner == missing
    assert "error" in wrong_owner


def test_late_shipment_gets_a_warning(order_lookup):
    summary = order_lookup.describe_order_status(8, "anacarol.ferreira@coldmail.com", TODAY)

    assert summary["status"] == "enviado"
    assert "warning" in summary


def test_cancelled_order_shows_the_reason(order_lookup):
    summary = order_lookup.describe_order_status(17, "matheus.correia@hayoo.com.br", TODAY)

    assert summary["status"] == "cancelado"
    assert "cancelado pelo cliente" in summary["notes"]


def test_installment_payment_is_readable(order_lookup):
    summary = order_lookup.describe_order_status(2, "thiago.barbosa@jmail.com", TODAY)

    assert summary["payment_method"] == "cartão de crédito em 6x"


@pytest.mark.parametrize(("order_id", "contact"), [(0, "a@b.com"), (-3, "a@b.com"), (1, " ")])
def test_invalid_input_is_rejected(order_lookup, order_id, contact):
    with pytest.raises(InvalidRequestError):
        order_lookup.find_verified_order(order_id, contact)


def test_old_delivered_order_is_out_of_the_regret_window(order_lookup):
    answer = order_lookup.check_return_request(
        5, "rafael.pereira@jmail.com", ReturnReason.REGRET, TODAY
    )

    assert answer["eligible"] is False
    assert answer["policy_section"] == "4.1"


def test_return_request_also_needs_the_owner(order_lookup):
    answer = order_lookup.check_return_request(5, "intruso@jmail.com", ReturnReason.REGRET, TODAY)

    assert "error" in answer
