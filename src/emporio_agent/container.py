import sqlite3
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from emporio_agent.application.agent import build_customer_agent, create_chat_model
from emporio_agent.application.catalog import CatalogService
from emporio_agent.application.chat import ChatSession
from emporio_agent.application.data_audit import DataAuditor
from emporio_agent.application.handoff import HandoffService
from emporio_agent.application.orders import OrderLookupService
from emporio_agent.application.prompts import build_system_prompt
from emporio_agent.application.tools import build_agent_tools
from emporio_agent.config import Settings
from emporio_agent.domain.pricing import PriceCalculator
from emporio_agent.domain.returns import ReturnPolicy
from emporio_agent.domain.store_hours import StoreSchedule
from emporio_agent.infrastructure.bm25_policy_search import Bm25PolicySearch
from emporio_agent.infrastructure.csv_repositories import (
    CsvCategoryRepository,
    CsvCustomerRepository,
    CsvOrderRepository,
    CsvProductRepository,
    CsvPromotionRepository,
)
from emporio_agent.infrastructure.jsonl_tickets import JsonlTicketRepository
from emporio_agent.infrastructure.policy_pdf import split_policy_into_sections
from emporio_agent.infrastructure.system_clock import SystemClock
from emporio_agent.ports.clock import Clock
from emporio_agent.ports.policy_search import PolicySearch


@dataclass(frozen=True)
class StoreServices:
    catalog: CatalogService
    order_lookup: OrderLookupService
    policy_search: PolicySearch
    schedule: StoreSchedule
    clock: Clock
    handoff: HandoffService


def load_store_services(settings: Settings) -> StoreServices:
    """Loads the data files and wires every service. Nothing here calls the LLM.

    This is the only place that knows the concrete classes, the rest of the code
    depends on the interfaces.

    Args:
        settings: Paths and time zone.

    Returns:
        The services ready to use.

    Raises:
        DataLoadError: If a data file is missing or invalid.
        ConfigurationError: If the time zone is unknown.
    """
    data = settings.data_dir
    products = CsvProductRepository(data / "products.csv")
    catalog = CatalogService(
        products,
        CsvCategoryRepository(data / "categories.csv"),
        CsvPromotionRepository(data / "promotions.csv"),
        PriceCalculator(),
    )
    order_lookup = OrderLookupService(
        CsvOrderRepository(data / "orders.csv", data / "order_items.csv"),
        CsvCustomerRepository(data / "customers.csv"),
        products,
        ReturnPolicy(),
    )
    policy_search = Bm25PolicySearch(split_policy_into_sections(data / "store_policies.pdf"))
    clock = SystemClock(settings.timezone)
    handoff = HandoffService(JsonlTicketRepository(settings.tickets_file), clock)
    return StoreServices(catalog, order_lookup, policy_search, StoreSchedule(), clock, handoff)


def build_data_auditor(settings: Settings) -> DataAuditor:
    """Loads the data files for the consistency checks. Nothing here calls the LLM.

    Args:
        settings: Location of the data folder.

    Returns:
        The auditor.

    Raises:
        DataLoadError: If a data file is missing or invalid.
    """
    data = settings.data_dir
    return DataAuditor(
        CsvProductRepository(data / "products.csv"),
        CsvCategoryRepository(data / "categories.csv"),
        CsvPromotionRepository(data / "promotions.csv"),
        CsvOrderRepository(data / "orders.csv", data / "order_items.csv"),
        CsvCustomerRepository(data / "customers.csv"),
    )


def open_conversation_store(settings: Settings) -> SqliteSaver:
    """Opens the SQLite file where conversations are saved, creating it if needed.

    Args:
        settings: Location of the database.

    Returns:
        A LangGraph checkpointer backed by SQLite.
    """
    settings.memory_db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.memory_db, check_same_thread=False)
    return SqliteSaver(connection)


def build_chat_agent(settings: Settings, checkpointer: Any | None = None) -> Any:
    """Builds the whole agent once, so many conversations can share it.

    Args:
        settings: Model, paths and limits.
        checkpointer: Where to save conversations. Defaults to the SQLite file.

    Returns:
        The compiled agent.

    Raises:
        ConfigurationError: If the model, key or data folder are not usable.
        DataLoadError: If a data file is missing or invalid.
    """
    settings.check_ready_to_chat()
    services = load_store_services(settings)
    tools = build_agent_tools(
        services.catalog,
        services.order_lookup,
        services.policy_search,
        services.schedule,
        services.clock,
        services.handoff,
    )
    return build_customer_agent(
        create_chat_model(settings.model, settings.temperature, settings.requests_per_minute),
        tools,
        build_system_prompt(services.clock.now()),
        checkpointer if checkpointer is not None else open_conversation_store(settings),
    )


def start_chat_session(
    settings: Settings, session_id: str, checkpointer: Any | None = None
) -> ChatSession:
    """Builds the agent and opens one conversation.

    Args:
        settings: Model, paths and limits.
        session_id: Conversation id, reuse it to continue an old conversation.
        checkpointer: Where to save the conversation. Defaults to the SQLite file.

    Returns:
        A ready ChatSession.

    Raises:
        ConfigurationError: If the model, key or data folder are not usable.
        DataLoadError: If a data file is missing or invalid.
    """
    agent = build_chat_agent(settings, checkpointer)
    return ChatSession(agent, session_id, settings.max_agent_steps)
