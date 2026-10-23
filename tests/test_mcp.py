import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from chilipad_mcp.server import create_server


def test_tools_schema_contains_no_token():
    async def check():
        tools = await create_server().list_tools()
        assert len(tools) == 15
        assert all("token" not in t.inputSchema.get("properties", {}) for t in tools)
        power = next(t for t in tools if t.name == "set_power")
        assert power.annotations.readOnlyHint is False
        assert set(power.inputSchema["required"]) == {"target", "on"}

    asyncio.run(check())


def test_real_stdio_handshake_and_validation():
    async def check():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "chilipad_mcp.cli", "serve"], env=dict(os.environ)
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "Unofficial Chilipad MCP"
                tools = await session.list_tools()
                assert len(tools.tools) == 15
                result = await session.call_tool(
                    "set_temperature", {"target": "my side", "value": 999, "unit": "F"}
                )
                assert "No rounding" in result.content[0].text

    asyncio.run(check())
