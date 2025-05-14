import os
import sys
import json
import asyncio
import logging
from contextlib import AsyncExitStack
from uagents import Agent, Context, Model
# Import MCP client machinery
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# CONFIG
AGENT_PORT = 8000
AGENT_NAME = "airbnb_mcp_uagent"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(AGENT_NAME)

class MCPRequest(Model):
    tool_name: str
    parameters: dict
    request_id: str

class MCPResponse(Model):
    success: bool
    result: object = None
    error: str = None
    request_id: str = None

class AirbnbMCPAgent:
    def __init__(self):
        self.agent = Agent(name=AGENT_NAME, port=AGENT_PORT, mailbox=True)
        self.mcp_exit_stack = None
        self.mcp_session = None
        self._setup_handlers()
        # Connect to MCP server on startup
        self.agent.on_event("startup")(self._on_startup)
        self.agent.on_event("shutdown")(self._on_shutdown)

    def _setup_handlers(self):
        @self.agent.on_message(MCPRequest, replies={MCPResponse})
        async def handle_mcp_request(ctx: Context, sender: str, msg: MCPRequest):
            ctx.logger.info(f"Received MCP request: {msg.tool_name} {msg.parameters}")
            try:
                if not self.mcp_session:
                    await self._connect_to_mcp()
                # Call the tool using the session
                result = await self._call_mcp_tool(msg.tool_name, msg.parameters)
                await ctx.send(sender, MCPResponse(success=True, result=result, request_id=msg.request_id))
            except Exception as e:
                ctx.logger.error(f"Error: {e}")
                await ctx.send(sender, MCPResponse(success=False, error=str(e), request_id=msg.request_id))

    async def _on_startup(self, ctx: Context):
        logger.info("Connecting to Airbnb MCP server on startup...")
        await self._connect_to_mcp()

    async def _on_shutdown(self, ctx: Context):
        logger.info("Shutting down MCP connection...")
        await self._cleanup_mcp_connection()

    async def _connect_to_mcp(self):
        self.mcp_exit_stack = AsyncExitStack()
        try:
            server_params = StdioServerParameters(
                command="npx",
                args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
                env={}
            )
            stdio_transport = await self.mcp_exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            self.mcp_session = await self.mcp_exit_stack.enter_async_context(ClientSession(stdio, write))
            await self.mcp_session.initialize()
            response = await self.mcp_session.list_tools()
            logger.info(f"Connected to Airbnb MCP server with tools: {[tool.name for tool in response.tools]}")
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {str(e)}")
            await self._cleanup_mcp_connection()
            raise

    async def _call_mcp_tool(self, tool_name, parameters):
        if not self.mcp_session:
            raise RuntimeError("MCP session is not initialized")
        logger.info(f"Calling MCP tool: {tool_name} with parameters: {parameters}")
        result = await self.mcp_session.call_tool(tool_name, parameters)
        # Ensure result is JSON serializable
        if hasattr(result, "dict") and callable(result.dict):
            return result.dict()
        elif hasattr(result, "__dict__"):
            return dict(result.__dict__)
        else:
            return result

    async def _cleanup_mcp_connection(self):
        if self.mcp_exit_stack:
            try:
                await self.mcp_exit_stack.aclose()
                logger.info("MCP connection closed")
            except Exception as e:
                logger.error(f"Error closing MCP connection: {str(e)}")
            self.mcp_exit_stack = None
            self.mcp_session = None

    def run(self):
        logger.info(f"uAgent address: {self.agent.address}")
        self.agent.run()

if __name__ == "__main__":
    agent = AirbnbMCPAgent()
    agent.run()
