import logging
from collections.abc import Callable
from importlib.resources import files

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from emporio_agent.application.chat import MAX_MESSAGE_LENGTH, ChatSession
from emporio_agent.errors import InvalidRequestError

logger = logging.getLogger(__name__)

SESSION_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
MAX_OPEN_SESSIONS = 500


class ChatRequest(BaseModel):
    session_id: str = Field(pattern=SESSION_ID_PATTERN, description="Conversation id")
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tools_used: list[str]


def create_web_app(open_session: Callable[[str], ChatSession]) -> FastAPI:
    """Builds the HTTP API and the small web chat page.

    Args:
        open_session: Function that opens a ChatSession for a session id. It is injected
            so tests can use a scripted model and production can use the real one.

    Returns:
        The FastAPI application.
    """
    app = FastAPI(
        title="Empório da Música — Customer Service Agent",
        description="Chat with Melody, the store's virtual assistant.",
        version="0.1.0",
    )
    sessions: dict[str, ChatSession] = {}

    def get_session(session_id: str) -> ChatSession:
        """Reuses the open session of an id, or opens a new one.

        Args:
            session_id: Conversation id.

        Returns:
            The ChatSession of that id.
        """
        if session_id not in sessions:
            # This is for keeping memory bounded, the oldest session leaves first
            if len(sessions) >= MAX_OPEN_SESSIONS:
                sessions.pop(next(iter(sessions)))
            sessions[session_id] = open_session(session_id)
        return sessions[session_id]

    @app.get("/health")
    def health() -> dict[str, str]:
        """Tells that the service is up.

        Returns:
            {"status": "ok"}.
        """
        return {"status": "ok"}

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        """Sends a customer message to the agent.

        Args:
            request: Session id and message.

        Returns:
            The agent reply and the tools it used.

        Raises:
            HTTPException: 422 for an invalid message, 503 when the model provider fails.
        """
        try:
            reply = get_session(request.session_id).send_message(request.message)
        except InvalidRequestError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            logger.exception("Agent call failed")
            raise HTTPException(
                status_code=503,
                detail="The assistant is unavailable right now, please try again soon.",
            ) from error
        return ChatResponse(
            session_id=request.session_id, reply=reply.text, tools_used=reply.tools_used
        )

    @app.get("/", response_class=HTMLResponse)
    def chat_page() -> str:
        """Serves the web chat page.

        Returns:
            The HTML of the page.
        """
        return files("emporio_agent.interfaces").joinpath("static/chat.html").read_text("utf-8")

    return app
