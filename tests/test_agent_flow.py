"""End to end tests of the agent loop with a scripted model, so no API key is needed."""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from emporio_agent.application.agent import build_customer_agent
from emporio_agent.application.chat import TOO_MANY_STEPS_REPLY, ChatSession
from emporio_agent.application.tools import build_agent_tools
from emporio_agent.config import Settings
from emporio_agent.container import load_store_services
from emporio_agent.errors import InvalidRequestError

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class ScriptedChatModel(BaseChatModel):
    """Fake chat model that answers with a fixed list of messages, in order."""

    replies: list[AIMessage]
    received: list[list[BaseMessage]] = []
    position: int = 0

    @property
    def _llm_type(self) -> str:
        """Names the model type for LangChain.

        Returns:
            Always "scripted".
        """
        return "scripted"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        """Returns the next scripted reply, repeating the last one when the script ends.

        Args:
            messages: Conversation sent by the agent, saved for assertions.
            stop: Ignored.
            run_manager: Ignored.
            **kwargs: Ignored.

        Returns:
            A ChatResult with the scripted message.
        """
        self.received.append(list(messages))
        reply = self.replies[min(self.position, len(self.replies) - 1)]
        self.position += 1
        if reply.tool_calls:
            # This is for giving every repeated tool call its own id, like a real model does
            calls = [{**call, "id": f"call_{self.position}"} for call in reply.tool_calls]
            reply = AIMessage(content=reply.content, tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=reply)])

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        """Pretends to bind tools, the script already knows which ones to call.

        Args:
            tools: Ignored.
            **kwargs: Ignored.

        Returns:
            The same model.
        """
        return self


def tool_call(name: str, args: dict[str, Any], call_id: str = "call_1") -> AIMessage:
    """Builds a model message that asks for one tool call.

    Args:
        name: Tool name.
        args: Tool arguments.
        call_id: Id of the call.

    Returns:
        An AIMessage with the tool call.
    """
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture(scope="module")
def tools():
    services = load_store_services(Settings(data_dir=DATA_DIR))
    return build_agent_tools(
        services.catalog,
        services.order_lookup,
        services.policy_search,
        services.schedule,
        services.clock,
    )


def open_session(tools, replies, max_steps: int = 25) -> tuple[ChatSession, ScriptedChatModel]:
    """Creates a session whose model follows a script.

    Args:
        tools: Agent tools.
        replies: Scripted model replies.
        max_steps: Recursion limit of the agent.

    Returns:
        The session and the model, to inspect what it received.
    """
    model = ScriptedChatModel(replies=replies, received=[])
    agent = build_customer_agent(model, tools, "test prompt", InMemorySaver())
    return ChatSession(agent, "test-session", max_steps), model


def test_agent_calls_a_tool_and_answers(tools):
    session, model = open_session(
        tools,
        [
            tool_call("get_product_details", {"product_name": "Takamine GD20"}),
            AIMessage(content="O Takamine GD20 sai por R$ 2.199,00."),
        ],
    )

    reply = session.send_message("Quanto custa o Takamine GD20?")

    assert reply.text == "O Takamine GD20 sai por R$ 2.199,00."
    assert reply.tools_used == ["get_product_details"]
    tool_result = model.received[1][-1].content
    assert "R$ 2.199,00" in tool_result


def test_conversation_is_remembered_in_the_same_session(tools):
    session, model = open_session(tools, [AIMessage(content="Oi!"), AIMessage(content="Claro!")])

    session.send_message("Oi, sou o Pedro")
    reply = session.send_message("Lembra meu nome?")

    assert reply.tools_used == []
    sent_texts = [message.content for message in model.received[-1]]
    assert "Oi, sou o Pedro" in sent_texts


def test_endless_tool_loop_ends_with_a_polite_reply(tools):
    loop = tool_call("get_store_status", {})
    session, _ = open_session(tools, [loop], max_steps=6)

    reply = session.send_message("Vocês estão abertos?")

    assert reply.text == TOO_MANY_STEPS_REPLY


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_empty_or_huge_messages_are_rejected(tools, message):
    session, _ = open_session(tools, [AIMessage(content="ok")])

    with pytest.raises(InvalidRequestError):
        session.send_message(message)
