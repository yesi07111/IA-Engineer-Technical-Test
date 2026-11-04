import functools
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from emporio_agent.application.catalog import CatalogService
from emporio_agent.application.handoff import HandoffService
from emporio_agent.application.orders import OrderLookupService
from emporio_agent.domain.models import TicketReason
from emporio_agent.domain.returns import ReturnReason
from emporio_agent.domain.store_hours import StoreSchedule
from emporio_agent.errors import InvalidRequestError
from emporio_agent.ports.clock import Clock
from emporio_agent.ports.policy_search import PolicySearch

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR = (
    "Internal error while looking this up. Apologize, do not guess the answer and offer the "
    "store contacts: WhatsApp (67) 3341-4444 or contato@emporiodamusica.com.br."
)


class SearchProductsInput(BaseModel):
    text: str | None = Field(
        None, description="Words to look for in name/description/specs, e.g. 'nylon', 'yamaha'"
    )
    category: str | None = Field(
        None, description="Category in Portuguese, e.g. 'violões', 'ukuleles', 'guitarras'"
    )
    max_price_brl: float | None = Field(None, ge=0, description="Highest price in BRL")
    min_price_brl: float | None = Field(None, ge=0, description="Lowest price in BRL")
    only_available: bool = Field(True, description="False also lists sold out products")
    limit: int = Field(10, ge=1, le=15, description="How many products to return")


class ProductNameInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=120, description="Product name or model")


class OrderInput(BaseModel):
    order_id: int = Field(gt=0, description="Order number given by the customer")
    customer_contact: str = Field(
        min_length=3, max_length=120, description="E-mail or phone used in the purchase"
    )


class ReturnInput(OrderInput):
    reason: ReturnReason = Field(
        description="regret = arrependimento, defect = defeito, preference = trocar cor/modelo"
    )


class PolicyQuestionInput(BaseModel):
    question: str = Field(
        min_length=2, max_length=300, description="The question rewritten in Portuguese"
    )


class NoInput(BaseModel):
    pass


class HandoffInput(BaseModel):
    reason: TicketReason = Field(
        description="complaint, return_request, late_delivery, product_request or other"
    )
    summary: str = Field(
        min_length=10,
        max_length=1000,
        description="What happened and what the customer wants, in Portuguese, for the team",
    )
    customer_contact: str = Field(
        min_length=3, max_length=120, description="E-mail or phone where the team can answer"
    )
    customer_name: str | None = Field(None, max_length=120)
    order_id: int | None = Field(None, gt=0, description="Related order number, if any")


def return_errors_to_agent(function: Callable[..., Any]) -> Callable[..., Any]:
    """Wraps a tool so errors come back as a message instead of breaking the conversation.

    Args:
        function: Tool function.

    Returns:
        The same function, but returning {"error": ...} when something goes wrong.
        Expected errors keep their message so the agent can fix the call. Unexpected
        errors are logged and replaced by a safe generic message.
    """

    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except InvalidRequestError as error:
            return {"error": str(error)}
        except Exception:
            logger.exception("Tool %s failed", function.__name__)
            return {"error": UNEXPECTED_ERROR}

    return wrapper


def build_agent_tools(
    catalog: CatalogService,
    order_lookup: OrderLookupService,
    policy_search: PolicySearch,
    schedule: StoreSchedule,
    clock: Clock,
    handoff: HandoffService | None = None,
) -> list[BaseTool]:
    """Creates the tools the agent can call, each one backed by a service.

    Args:
        catalog: Products, prices and promotions.
        order_lookup: Orders and returns, with identity check.
        policy_search: Search over the policy manual.
        schedule: Opening hours.
        clock: Current time in the store's time zone.
        handoff: Ticket service for the store team. Without it the agent only shares the
            store contacts.

    Returns:
        The tools, ready to give to the agent.
    """

    def search_products(
        text: str | None = None,
        category: str | None = None,
        max_price_brl: float | None = None,
        min_price_brl: float | None = None,
        only_available: bool = True,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Searches the instrument catalog with filters, cheapest first.

        Args:
            text: Words to look for.
            category: Category name.
            max_price_brl: Highest price.
            min_price_brl: Lowest price.
            only_available: Hide products that can not be bought.
            limit: Number of products.

        Returns:
            Total found and the products with prices and availability.
        """
        return catalog.search_products(
            text, category, max_price_brl, min_price_brl, only_available, limit
        )

    def get_product_details(product_name: str) -> dict[str, Any]:
        """Gets price, promotion, PIX price, installments, stock and specs of one product.

        Args:
            product_name: Name or model.

        Returns:
            The product, or candidates/closest names when it is not clear.
        """
        return catalog.describe_product(product_name)

    def list_active_promotions() -> list[dict[str, Any]]:
        """Lists the promotions running now.

        Returns:
            Each promotion with its product and prices.
        """
        return catalog.list_active_promotions()

    def list_categories() -> list[dict[str, Any]]:
        """Lists the catalog categories and how many products are available in each.

        Returns:
            Categories with available product counts.
        """
        return catalog.list_categories()

    def get_order_status(order_id: int, customer_contact: str) -> dict[str, Any]:
        """Gets status, tracking code, delivery estimate and items of an order.

        Args:
            order_id: Order number.
            customer_contact: E-mail or phone used in the purchase.

        Returns:
            The order summary or an error when it can not be verified.
        """
        return order_lookup.describe_order_status(order_id, customer_contact, clock.now().date())

    def check_return_eligibility(
        order_id: int, customer_contact: str, reason: ReturnReason
    ) -> dict[str, Any]:
        """Checks if an order can still be returned or exchanged.

        Args:
            order_id: Order number.
            customer_contact: E-mail or phone used in the purchase.
            reason: regret, defect or preference.

        Returns:
            Eligibility, policy section and explanation.
        """
        return order_lookup.check_return_request(
            order_id, customer_contact, ReturnReason(reason), clock.now().date()
        )

    def search_store_policies(question: str) -> list[dict[str, str]] | dict[str, str]:
        """Searches the store policy manual.

        Args:
            question: Question in Portuguese.

        Returns:
            Up to 3 sections with number, title and text, or a note when nothing matched.
        """
        sections = policy_search.search(question, limit=3)
        if not sections:
            return {"note": "Nothing found. Try other Portuguese words, or say you don't know."}
        return [{"section": s.number, "title": s.title, "text": s.text} for s in sections]

    def get_store_status() -> dict[str, Any]:
        """Tells the current date and time in Campo Grande and if the store is open.

        Returns:
            Current moment, open flag, weekly hours and the next opening.
        """
        now = clock.now()
        return {
            "now": now.strftime("%Y-%m-%d %H:%M (%A)"),
            "open_now": schedule.is_open_at(now),
            "hours": schedule.describe_hours(),
            "next_opening": schedule.describe_next_opening(now),
        }

    def forward_to_team(
        reason: TicketReason,
        summary: str,
        customer_contact: str,
        config: RunnableConfig,
        customer_name: str | None = None,
        order_id: int | None = None,
    ) -> dict[str, Any]:
        """Opens a ticket so a person from the team continues the case.

        Args:
            reason: Kind of case.
            summary: Case summary for the team.
            customer_contact: E-mail or phone to answer.
            config: Run config injected by LangChain, used to read the session id.
            customer_name: Customer name, if known.
            order_id: Related order, if any.

        Returns:
            Ticket number and expected response time.
        """
        assert handoff is not None
        session_id = config.get("configurable", {}).get("thread_id")
        return handoff.open_ticket(
            TicketReason(reason), summary, customer_contact, customer_name, order_id, session_id
        )

    # This is the description the model reads to decide which tool fits each question
    catalog_of_tools: list[tuple[Callable[..., Any], type[BaseModel], str]] = [
        (
            search_products,
            SearchProductsInput,
            "Search instruments by category, words and budget. Use for 'which options do you "
            "have', 'violões até R$1000', etc.",
        ),
        (
            get_product_details,
            ProductNameInput,
            "Price, promotion, PIX price, installments, stock and specs of ONE product. "
            "ALWAYS call it before telling a price or availability.",
        ),
        (list_active_promotions, NoInput, "Promotions that are active right now."),
        (list_categories, NoInput, "Categories of instruments the store sells."),
        (
            get_order_status,
            OrderInput,
            "Status, tracking and delivery of an order. Needs the order number AND the e-mail "
            "or phone of the purchase; ask the customer for both if missing.",
        ),
        (
            check_return_eligibility,
            ReturnInput,
            "Checks if an order can be returned/exchanged (regret, defect or preference). "
            "Needs order number and e-mail or phone.",
        ),
        (
            search_store_policies,
            PolicyQuestionInput,
            "Store manual: returns, exchanges, warranty, shipping, payment, installments, "
            "address, contacts, hours, privacy. Write the question in Portuguese.",
        ),
        (get_store_status, NoInput, "Current time in Campo Grande and if the store is open."),
    ]
    if handoff is not None:
        catalog_of_tools.append(
            (
                forward_to_team,
                HandoffInput,
                "Hands the case to a person of the store team (complaints, return or exchange "
                "requests, late deliveries, products the customer wants that we don't have, "
                "anything you can't solve). Confirm with the customer and get an e-mail or "
                "phone before calling it. Tell the customer the ticket number.",
            )
        )
    return [
        StructuredTool.from_function(
            func=return_errors_to_agent(function),
            name=function.__name__,
            description=description,
            args_schema=schema,
            handle_validation_error=True,
        )
        for function, schema, description in catalog_of_tools
    ]
