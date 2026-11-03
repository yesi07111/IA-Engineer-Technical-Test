from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.application.orders import OrderLookupService
from emporio_agent.application.tools import UNEXPECTED_ERROR, build_agent_tools
from emporio_agent.domain.returns import ReturnPolicy
from emporio_agent.domain.store_hours import StoreSchedule
from emporio_agent.infrastructure.bm25_policy_search import Bm25PolicySearch
from emporio_agent.infrastructure.policy_pdf import split_policy_into_sections
from emporio_agent.ports.clock import Clock

POLICY_PDF = Path(__file__).resolve().parents[1] / "data" / "store_policies.pdf"


class FrozenClock(Clock):
    """Clock stuck at a fixed moment, so tests do not depend on today's date."""

    def __init__(self, moment: datetime) -> None:
        """Freezes the clock.

        Args:
            moment: The moment now() will always return.
        """
        self._moment = moment

    def now(self) -> datetime:
        """Gets the frozen moment.

        Returns:
            Always the same datetime.
        """
        return self._moment


@pytest.fixture(scope="module")
def tools(catalog, orders, customers, products):
    clock = FrozenClock(datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande")))
    order_lookup = OrderLookupService(orders, customers, products, ReturnPolicy())
    policy_search = Bm25PolicySearch(split_policy_into_sections(POLICY_PDF))
    built = build_agent_tools(catalog, order_lookup, policy_search, StoreSchedule(), clock)
    return {tool.name: tool for tool in built}


def test_all_tools_are_exposed(tools):
    assert set(tools) == {
        "search_products",
        "get_product_details",
        "list_active_promotions",
        "list_categories",
        "get_order_status",
        "check_return_eligibility",
        "search_store_policies",
        "get_store_status",
    }


def test_product_details_tool(tools):
    answer = tools["get_product_details"].invoke({"product_name": "takamine gd20"})

    assert answer["result"] == "found"


def test_search_tool_with_budget(tools):
    answer = tools["search_products"].invoke({"category": "violões", "max_price_brl": 1000})

    assert answer["total_found"] == 12


def test_invalid_category_comes_back_as_an_error_message(tools):
    answer = tools["search_products"].invoke({"category": "amplificadores"})

    assert "Valid categories" in answer["error"]


def test_schema_validation_errors_do_not_raise(tools):
    answer = tools["get_order_status"].invoke({"order_id": -1, "customer_contact": "x@y.com"})

    assert isinstance(answer, str)
    assert "validation" in answer.lower()


def test_order_status_tool(tools):
    answer = tools["get_order_status"].invoke(
        {"order_id": 8, "customer_contact": "(67) 99654-7821"}
    )

    assert answer["status"] == "enviado"


def test_return_tool_accepts_the_reason_as_text(tools):
    answer = tools["check_return_eligibility"].invoke(
        {"order_id": 1, "customer_contact": "pedro.oliveira@jmail.com", "reason": "regret"}
    )

    assert answer["eligible"] is False


def test_policy_tool_returns_sections(tools):
    answer = tools["search_store_policies"].invoke({"question": "posso devolver?"})

    assert "4.1" in [section["section"] for section in answer]


def test_policy_tool_without_matches_says_so(tools):
    answer = tools["search_store_policies"].invoke({"question": "capital da frança"})

    assert "note" in answer


def test_store_status_tool(tools):
    answer = tools["get_store_status"].invoke({})

    assert answer["open_now"] is True
    assert answer["next_opening"] == "amanhã às 09:00"


def test_unexpected_errors_are_hidden_from_the_customer(catalog, orders, customers, products):
    class BrokenSearch(Bm25PolicySearch):
        """Policy search that always fails, to test the error wrapper."""

        def search(self, question, limit=3):
            """Fails on purpose.

            Args:
                question: Ignored.
                limit: Ignored.

            Raises:
                RuntimeError: Always.
            """
            raise RuntimeError("disk on fire")

    broken = BrokenSearch(split_policy_into_sections(POLICY_PDF))
    clock = FrozenClock(datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande")))
    order_lookup = OrderLookupService(orders, customers, products, ReturnPolicy())
    built = build_agent_tools(catalog, order_lookup, broken, StoreSchedule(), clock)
    policy_tool = next(tool for tool in built if tool.name == "search_store_policies")

    assert policy_tool.invoke({"question": "horário"}) == {"error": UNEXPECTED_ERROR}
