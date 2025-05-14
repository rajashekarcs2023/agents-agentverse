import threading
import logging
from datetime import datetime, timezone
from uuid import uuid4
import json
from typing import Any

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    StartSessionContent,
    EndSessionContent,
)
from openai import OpenAI

from mcp_protocol import (
    ListTools,
    ListToolsResponse,
    CallTool,
    CallToolResponse,
    mcp_protocol_spec
)


class MCPAdapter:
    def __init__(self, mcp_server, openai_api_key: str):
        self.mcp = mcp_server
        self.openai_client = OpenAI(api_key=openai_api_key)

        # Create protocols (do not include yet)
        self.mcp_proto = Protocol(spec=mcp_protocol_spec, role="server")
        self.chat_proto = Protocol(name="AgentChatProtocol", version="0.3.0", spec=chat_protocol_spec)

        # Register handlers
        self._setup_mcp_protocol_handlers()
        self._setup_chat_protocol_handlers()

    @property
    def protocols(self) -> list[Protocol]:
        return [self.mcp_proto, self.chat_proto]

    def _setup_mcp_protocol_handlers(self):
        @self.mcp_proto.on_message(model=ListTools)
        async def list_tools(ctx: Context, sender: str, msg: ListTools):
            ctx.logger.info("Received ListTools request")
            tools = await self.mcp.list_tools()

            raw_tools = [
                {"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema}
                for tool in tools
            ]

            await ctx.send(sender, ListToolsResponse(tools=raw_tools))

        @self.mcp_proto.on_message(model=CallTool)
        async def call_tool(ctx: Context, sender: str, msg: CallTool):
            ctx.logger.info(f"Calling tool: {msg.tool} with args: {msg.args}")
            try:
                output = await self.mcp.call_tool(msg.tool, msg.args)
                result = "\n".join(str(r) for r in output) if isinstance(output, list) else str(output)
                await ctx.send(sender, CallToolResponse(message=result))
            except Exception as e:
                error = f"Error: {str(e)}"
                ctx.logger.error(error)
                await ctx.send(sender, CallToolResponse(message=error))

    def _setup_chat_protocol_handlers(self):
        @self.chat_proto.on_message(model=ChatMessage)
        async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
            ack = ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id
            )
            await ctx.send(sender, ack)

            for item in msg.content:
                if isinstance(item, StartSessionContent):
                    ctx.logger.info(f"Got a start session message from {sender}")
                    continue
                elif isinstance(item, TextContent):
                    ctx.logger.info(f"Got a message from {sender}: {item.text}")
                    try:
                        tools = await self.mcp.list_tools()
                        available_tools = [{
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema
                            }
                        } for tool in tools]

                        completion = self.openai_client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": item.text}],
                            tools=available_tools
                        )

                        tool_calls = completion.choices[0].message.tool_calls
                        if tool_calls:
                            tool_call = tool_calls[0]
                            selected_tool = tool_call.function.name
                            tool_args = json.loads(tool_call.function.arguments)
                            try:
                                tool_results = await self.mcp.call_tool(selected_tool, tool_args)
                                response_text = "\n".join(str(r) for r in tool_results)
                            except Exception as e:
                                response_text = f"Failed to call tool {selected_tool}: {str(e)}"
                        else:
                            response_text = completion.choices[0].message.content or "No response."

                        await ctx.send(sender, ChatMessage(
                            timestamp=datetime.now(timezone.utc),
                            msg_id=uuid4(),
                            content=[TextContent(type="text", text=response_text)]
                        ))

                    except Exception as e:
                        error_msg = f"Error processing query: {str(e)}"
                        ctx.logger.error(error_msg)
                        await ctx.send(sender, ChatMessage(
                            timestamp=datetime.now(timezone.utc),
                            msg_id=uuid4(),
                            content=[TextContent(type="text", text=error_msg)]
                        ))
                else:
                    ctx.logger.info(f"Got unexpected content from {sender}")

        @self.chat_proto.on_message(model=ChatAcknowledgement)
        async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
            ctx.logger.info(f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}")
            if msg.metadata:
                ctx.logger.info(f"Metadata: {msg.metadata}")

    def run(self, agent: Agent):
        try:
            logging.info("🚀 Starting MCP Server and Agent...")

            # Run agent in thread
            agent_thread = threading.Thread(target=agent.run, daemon=True)
            agent_thread.start()

            # Start MCP server
            self.mcp.run(transport='stdio')

        except Exception as e:
            logging.error(f"❌ Error running agent or MCP: {str(e)}")