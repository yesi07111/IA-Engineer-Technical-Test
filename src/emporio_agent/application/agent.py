from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from emporio_agent.errors import ConfigurationError


def create_chat_model(
    model_id: str, temperature: float | None = None, requests_per_minute: float | None = None
) -> BaseChatModel:
    """Creates the LLM client for any provider supported by LangChain.

    Args:
        model_id: Model in "provider:model" format, e.g. "anthropic:claude-sonnet-5-5".
        temperature: Sampling temperature. None keeps the provider default, which is
            required by models that do not accept a custom temperature.
        requests_per_minute: Max calls per minute to the provider, e.g. 5 for a free
            tier. None means no limit.

    Returns:
        The chat model, with retries for temporary provider errors.

    Raises:
        ConfigurationError: If the provider is unknown or its package is not installed.
    """
    # This is for only sending temperature when it was set, some models reject it
    options: dict[str, Any] = {"temperature": temperature} if temperature is not None else {}
    if requests_per_minute:
        # This works like a queue, calls wait their turn instead of failing with a 429
        options["rate_limiter"] = InMemoryRateLimiter(
            requests_per_second=requests_per_minute / 60, check_every_n_seconds=0.2
        )
    try:
        return init_chat_model(model_id, max_retries=3, **options)
    except ImportError as error:
        raise ConfigurationError(
            f"The package for '{model_id}' is not installed. Install the matching extra, "
            "e.g. pip install -e .[anthropic]"
        ) from error
    except ValueError as error:
        raise ConfigurationError(f"Can not use the model '{model_id}': {error}") from error


def build_customer_agent(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    system_prompt: str,
    checkpointer: Checkpointer | None = None,
) -> Any:
    """Builds the tool calling (ReAct) agent that talks to customers.

    Args:
        model: Chat model that supports tool calling.
        tools: Tools the agent can call.
        system_prompt: Persona and rules.
        checkpointer: Where conversations are saved, None keeps nothing between runs.

    Returns:
        A compiled LangGraph agent that receives {"messages": [...]}.
    """
    return create_agent(
        model=model,
        tools=list(tools),
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        name="emporio_customer_agent",
    )
