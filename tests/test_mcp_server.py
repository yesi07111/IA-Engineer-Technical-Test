import asyncio
import json

import pytest

from emporio_agent.interfaces.mcp_server import build_mcp_server
from tests.test_web import tools  # noqa: F401  (shared fixture)


@pytest.fixture(scope="module")
def server(tools):  # noqa: F811
    return build_mcp_server(tools)


def result_text(result):
    """Gets the text content of an MCP tool result.

    Args:
        result: Result of call_tool.

    Returns:
        The concatenated text parts.
    """
    content = getattr(result, "content", result)
    return "".join(getattr(part, "text", "") for part in content)


def test_every_agent_tool_is_exposed(server, tools):  # noqa: F811
    listed = asyncio.run(server.list_tools())

    assert {tool.name for tool in listed} == {tool.name for tool in tools}


def test_tool_schema_keeps_argument_names(server):
    listed = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    schema = listed["get_order_status"].input_schema
    assert set(schema["required"]) == {"order_id", "customer_contact"}
    assert "e-mail or phone" in schema["properties"]["customer_contact"]["description"].lower()


def test_calling_a_tool_returns_json(server):
    result = asyncio.run(server.call_tool("get_product_details", {"product_name": "Takamine GD20"}))

    answer = json.loads(result_text(result))
    assert answer["product"]["price"]["list_price"] == "R$ 2.199,00"


def test_optional_arguments_can_be_left_out(server):
    result = asyncio.run(server.call_tool("search_products", {"category": "ukuleles"}))

    assert json.loads(result_text(result))["total_found"] == 14
