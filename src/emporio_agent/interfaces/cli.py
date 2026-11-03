import logging
import uuid

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

from emporio_agent.application.chat import ChatSession
from emporio_agent.config import Settings
from emporio_agent.container import load_store_services, start_chat_session
from emporio_agent.errors import EmporioError, InvalidRequestError

app = typer.Typer(help="Empório da Música customer service agent.", no_args_is_help=True)
console = Console()

EXIT_WORDS = {"exit", "quit", "sair", "tchau"}


def load_settings() -> Settings:
    """Reads .env into the environment and builds the settings.

    Returns:
        The settings.

    Raises:
        typer.Exit: If a setting is invalid, after printing why.
    """
    load_dotenv()
    try:
        return Settings()
    except ValueError as error:
        console.print(f"[red]Invalid configuration:[/red] {error}")
        raise typer.Exit(code=2) from error


def answer_one_message(session: ChatSession, text: str, show_tools: bool) -> None:
    """Sends one message and prints the answer, without letting errors close the chat.

    Args:
        session: Open conversation.
        text: Customer message.
        show_tools: Also print which tools the agent used.
    """
    try:
        with console.status("Melody está digitando..."):
            reply = session.send_message(text)
    except InvalidRequestError as error:
        console.print(f"[yellow]{error}[/yellow]")
        return
    except Exception as error:  # provider errors: network, auth, rate limits
        logging.getLogger(__name__).debug("Agent call failed", exc_info=True)
        details = str(error).splitlines()[0][:200] if str(error) else ""
        console.print(
            f"[red]The model call failed ({type(error).__name__}: {details}).[/red] "
            "Check your connection, API key and EMPORIO_MODEL, then try again."
        )
        return

    console.print(Markdown(f"**Melody:** {reply.text}"))
    if show_tools and reply.tools_used:
        console.print(f"[dim]tools: {', '.join(reply.tools_used)}[/dim]")


@app.command()
def chat(
    session: str = typer.Option(None, help="Session id to continue an old conversation."),
    show_tools: bool = typer.Option(False, "--show-tools", help="Print the tools used."),
    verbose: bool = typer.Option(False, "--verbose", help="Print debug logs."),
) -> None:
    """Opens an interactive conversation with the agent.

    Args:
        session: Session id to reuse, a new one is created when empty.
        show_tools: Print the tools used on each answer.
        verbose: Show debug logs.
    """
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)
    settings = load_settings()
    session_id = session or uuid.uuid4().hex[:8]
    try:
        chat_session = start_chat_session(settings, session_id)
    except EmporioError as error:
        console.print(f"[red]Could not start the agent:[/red] {error}")
        raise typer.Exit(code=1) from error

    console.print(
        f"[bold]Empório da Música[/bold] · model {settings.model} · session [cyan]{session_id}"
        "[/cyan]\n[dim]Type 'sair' to quit. Use --session with this id to continue later.[/dim]"
    )
    while True:
        try:
            text = console.input("[bold cyan]Você:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if text.lower() in EXIT_WORDS:
            break
        if text:
            answer_one_message(chat_session, text, show_tools)
    console.print("[dim]Até logo![/dim]")


@app.command()
def check() -> None:
    """Loads every data file and prints a summary, without calling the model.

    Useful to confirm the data folder is fine before chatting.
    """
    settings = load_settings()
    try:
        services = load_store_services(settings)
    except EmporioError as error:
        console.print(f"[red]Data problem:[/red] {error}")
        raise typer.Exit(code=1) from error

    categories = services.catalog.list_categories()
    available = sum(category["available_products"] for category in categories)
    promotions = services.catalog.list_active_promotions()
    console.print(f"[green]Data OK[/green] · {len(categories)} categories")
    console.print(f"{available} products available · {len(promotions)} active promotions")
    console.print(f"Store open now: {services.schedule.is_open_at(services.clock.now())}")
    try:
        settings.check_ready_to_chat()
        console.print(f"[green]Model settings OK[/green] · {settings.model}")
    except EmporioError as error:
        console.print(f"[yellow]Model not ready:[/yellow] {error}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Address to listen on."),
    port: int = typer.Option(8000, help="Port to listen on."),
) -> None:
    """Starts the HTTP API and the web chat page (needs the "web" extra).

    Args:
        host: Address to listen on.
        port: Port to listen on.
    """
    try:
        import uvicorn

        from emporio_agent.interfaces.web import create_web_app
    except ImportError as error:
        console.print('[red]Install the web extra first:[/red] pip install -e ".[web]"')
        raise typer.Exit(code=1) from error

    settings = load_settings()
    try:
        settings.check_ready_to_chat()
    except EmporioError as error:
        console.print(f"[red]Could not start the agent:[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"Web chat on http://{host}:{port}")
    uvicorn.run(
        create_web_app(lambda session_id: start_chat_session(settings, session_id)),
        host=host,
        port=port,
    )


if __name__ == "__main__":
    app()
