import inspect
import json
from collections.abc import Callable, Sequence
from typing import Annotated, Any

from langchain_core.tools import BaseTool
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

SERVER_INSTRUCTIONS = (
    "Tools of Empório da Música, a musical instrument store in Campo Grande/MS, Brazil: "
    "catalog search, prices with promotions and PIX, order status with identity check, "
    "return eligibility, store policies and opening hours. Answers are in Portuguese."
)


def make_mcp_handler(tool: BaseTool) -> Callable[..., str]:
    """Wraps a LangChain tool as a plain function with the same arguments.

    MCP reads the function signature to build the tool schema, so the signature is
    copied from the tool's argument model.

    Args:
        tool: Tool built by build_agent_tools.

    Returns:
        A function that runs the tool and returns its result as JSON text.
    """

    def handler(**arguments: Any) -> str:
        """Runs the tool with the arguments sent by the MCP client.

        Args:
            **arguments: Tool arguments.

        Returns:
            The tool result as JSON text.
        """
        result = tool.invoke({k: v for k, v in arguments.items() if v is not None})
        return json.dumps(result, ensure_ascii=False, default=str)

    schema = tool.tool_call_schema
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        raise TypeError(f"Tool {tool.name} needs a Pydantic v2 argument model")
    fields = schema.model_fields
    annotations = {
        name: Annotated[field.annotation, Field(description=field.description or name)]
        for name, field in fields.items()
    }
    # This is for MCP to see the real argument names and types instead of **arguments
    handler.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                annotation=annotations[name],
                default=inspect.Parameter.empty if field.is_required() else field.default,
            )
            for name, field in fields.items()
        ]
    )
    handler.__annotations__ = dict(annotations)
    handler.__annotations__["return"] = str
    handler.__name__ = tool.name
    return handler


def build_mcp_server(tools: Sequence[BaseTool]) -> MCPServer:
    """Creates an MCP server that exposes the agent tools.

    Any MCP client (Claude Desktop, IDE assistants, other agents) can then use the store
    data and rules with the same validation and privacy checks as the chat agent.

    Args:
        tools: Tools built by build_agent_tools.

    Returns:
        The MCP server, ready to run over stdio.
    """
    server = MCPServer(name="emporio-da-musica", instructions=SERVER_INSTRUCTIONS)
    for tool in tools:
        server.add_tool(
            make_mcp_handler(tool),
            name=tool.name,
            description=tool.description,
            structured_output=False,
        )
    return server
