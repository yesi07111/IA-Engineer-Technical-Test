from datetime import date

from emporio_agent.domain.models import OrderStatus
from emporio_agent.domain.returns import ReturnPolicy, ReturnReason
from tests.factories import make_order

DELIVERED_ON = date(2026, 3, 5)
BOUGHT_ON = date(2026, 3, 1)


def decide(reason, today, **order_fields):
    """Runs the return policy on a test order.

    Args:
        reason: Return reason.
        today: Date used as today.
        **order_fields: Overrides for the test order.

    Returns:
        The ReturnDecision.
    """
    order = make_order(order_date=BOUGHT_ON, estimated_delivery=DELIVERED_ON, **order_fields)
    return ReturnPolicy().check_return_eligebility_window(order, reason, today)


def test_regret_on_the_seventh_day_is_accepted():
    decision = decide(ReturnReason.REGRET, date(2026, 3, 12))

    assert decision.eligible
    assert decision.policy_section == "4.1"
    assert decision.days_counted == 7


def test_regret_on_the_eighth_day_is_refused():
    assert not decide(ReturnReason.REGRET, date(2026, 3, 13)).eligible


def test_preference_exchange_uses_section_4_3():
    assert decide(ReturnReason.PREFERENCE, date(2026, 3, 6)).policy_section == "4.3"


def test_defect_counts_from_the_purchase_date():
    assert decide(ReturnReason.DEFECT, date(2026, 3, 31)).eligible
    late = decide(ReturnReason.DEFECT, date(2026, 4, 1))
    assert not late.eligible
    assert "fabricante" in late.explanation


def test_defect_after_legal_warranty_mentions_it():
    decision = decide(ReturnReason.DEFECT, date(2026, 8, 1))

    assert "já terminou" in decision.explanation


def test_order_not_delivered_yet_can_not_be_returned():
    decision = decide(ReturnReason.REGRET, date(2026, 3, 6), status=OrderStatus.SHIPPED)

    assert not decision.eligible
    assert "ainda não foi entregue" in decision.explanation


def test_cancelled_order_can_not_be_returned():
    assert not decide(ReturnReason.REGRET, date(2026, 3, 6), status=OrderStatus.CANCELLED).eligible


def test_future_delivery_date_never_gives_negative_days():
    decision = decide(ReturnReason.REGRET, date(2026, 3, 2))

    assert decision.days_counted == 0
