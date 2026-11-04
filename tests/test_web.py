import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from emporio_agent.application.chat import AgentReply
from emporio_agent.errors import InvalidRequestError
from emporio_agent.interfaces.web import create_web_app
from tests.test_agent_flow import open_session, tool_call


class FailingSession:
    """Session that always fails like a provider outage, to test the error mapping."""

    def send_message(self, text):
        """Fails on purpose.

        Args:
            text: Ignored.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("provider down")


@pytest.fixture
def client(tools):
    replies = [
        tool_call("get_store_status", {}),
        AIMessage(content="Estamos abertos até as 18:00!"),
    ]
    return TestClient(create_web_app(lambda session_id: open_session(tools, replies)[0]))


@pytest.fixture(scope="module")
def tools():
    from emporio_agent.application.tools import build_agent_tools
    from emporio_agent.config import Settings
    from emporio_agent.container import load_store_services
    from tests.test_agent_flow import DATA_DIR

    services = load_store_services(Settings(data_dir=DATA_DIR))
    return build_agent_tools(
        services.catalog,
        services.order_lookup,
        services.policy_search,
        services.schedule,
        services.clock,
    )


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_reply_and_tools(client):
    response = client.post("/api/chat", json={"session_id": "abc-1", "message": "Estão abertos?"})

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "abc-1",
        "reply": "Estamos abertos até as 18:00!",
        "tools_used": ["get_store_status"],
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"session_id": "abc", "message": ""},
        {"session_id": "abc", "message": "x" * 2001},
        {"session_id": "../etc", "message": "oi"},
        {"message": "oi"},
    ],
)
def test_invalid_requests_are_rejected(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 422


def test_whitespace_only_message_is_rejected():
    class StrictSession:
        """Session that rejects every message like an empty one."""

        def send_message(self, text):
            """Rejects the message.

            Args:
                text: Ignored.

            Raises:
                InvalidRequestError: Always.
            """
            raise InvalidRequestError("Empty message.")

    client = TestClient(create_web_app(lambda session_id: StrictSession()))

    response = client.post("/api/chat", json={"session_id": "s1", "message": "   "})

    assert response.status_code == 422
    assert response.json()["detail"] == "Empty message."


def test_provider_failure_becomes_503_without_details():
    client = TestClient(create_web_app(lambda session_id: FailingSession()))

    response = client.post("/api/chat", json={"session_id": "s1", "message": "oi"})

    assert response.status_code == 503
    assert "provider down" not in response.text


def test_same_session_id_reuses_the_conversation():
    opened = []

    class CountingSession:
        """Session that records how many times it was opened."""

        def send_message(self, text):
            """Answers with a fixed reply.

            Args:
                text: Ignored.

            Returns:
                A fixed AgentReply.
            """
            return AgentReply(text="ok")

    def open_counting(session_id):
        opened.append(session_id)
        return CountingSession()

    client = TestClient(create_web_app(open_counting))
    client.post("/api/chat", json={"session_id": "same", "message": "1"})
    client.post("/api/chat", json={"session_id": "same", "message": "2"})

    assert opened == ["same"]


def test_chat_page_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Empório da Música" in response.text
