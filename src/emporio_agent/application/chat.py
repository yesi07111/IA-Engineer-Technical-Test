from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from emporio_agent.application.prompts import STORE_CONTACT
from emporio_agent.errors import InvalidRequestError

MAX_MESSAGE_LENGTH = 2000
TOO_MANY_STEPS_REPLY = (
    "Desculpe, não consegui concluir essa consulta agora. Pode reformular a pergunta? "
    f"Se preferir, fale com a equipe: {STORE_CONTACT}."
)


@dataclass(frozen=True)
class AgentReply:
    text: str
    tools_used: list[str] = field(default_factory=list)


def read_message_text(message: BaseMessage) -> str:
    """Gets the plain text of a model message.

    Some providers return the content as a list of blocks instead of a string.

    Args:
        message: Message from the model.

    Returns:
        Only the text parts, joined.
    """
    if isinstance(message.content, str):
        return message.content
    parts = [
        block.get("text", "") if isinstance(block, dict) else str(block)
        for block in message.content
    ]
    return "".join(parts)


def collect_turn_results(messages: list[BaseMessage]) -> AgentReply:
    """Extracts the final answer and the tools used in the last turn.

    Args:
        messages: Whole conversation state after the agent ran.

    Returns:
        The last AI answer and the tools called since the last customer message.
    """
    last_human = max(
        (index for index, message in enumerate(messages) if isinstance(message, HumanMessage)),
        default=-1,
    )
    turn = messages[last_human + 1 :]
    tools_used = [message.name or "tool" for message in turn if isinstance(message, ToolMessage)]
    answers = [message for message in turn if isinstance(message, AIMessage)]
    text = read_message_text(answers[-1]).strip() if answers else ""
    return AgentReply(text=text or TOO_MANY_STEPS_REPLY, tools_used=tools_used)


class ChatSession:
    """One conversation with the agent, identified by a session id.

    The id is the LangGraph thread id, so using the same id again continues the
    conversation when the agent has a persistent checkpointer.
    """

    def __init__(self, agent: Any, session_id: str, max_agent_steps: int = 25) -> None:
        """Prepares the session.

        Args:
            agent: Compiled agent from build_customer_agent.
            session_id: Conversation id.
            max_agent_steps: Max graph steps per message, stops tool call loops.
        """
        self._agent = agent
        self.session_id = session_id
        self._config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": max_agent_steps,
        }

    def send_message(self, text: str) -> AgentReply:
        """Sends a customer message and waits for the answer.

        Args:
            text: What the customer wrote.

        Returns:
            The answer and the tools the agent used to build it.

        Raises:
            InvalidRequestError: If the message is empty or too long.
            Exception: Provider errors (network, auth, rate limit) are not hidden here,
                the interface decides how to show them.
        """
        text = (text or "").strip()
        if not text:
            raise InvalidRequestError("Empty message.")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise InvalidRequestError(
                f"Message too long ({len(text)} characters, max {MAX_MESSAGE_LENGTH})."
            )
        try:
            state = self._agent.invoke(
                {"messages": [{"role": "user", "content": text}]}, config=self._config
            )
        except GraphRecursionError:
            return AgentReply(text=TOO_MANY_STEPS_REPLY)
        return collect_turn_results(state["messages"])
