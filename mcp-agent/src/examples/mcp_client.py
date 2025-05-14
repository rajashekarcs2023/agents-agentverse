#!/usr/bin/env python3
# src/examples/mcp_client.py

import sys
import os
import json
import logging
from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

# Add parent directory to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import MCP protocol models for tool calling
from mcp_protocol import (
    MCPListToolsRequest,
    MCPListToolsResponse,
    MCPCallToolRequest,
    MCPCallToolResponse,
    mcp_protocol
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_client")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.examples.mcp_client <server_address> [message_or_command] [arguments_json]")
        print("\nExamples:")
        print("  python -m src.examples.mcp_client agent1q... 'Hello from MCP Client!'")
        print("  python -m src.examples.mcp_client agent1q... list")
        print("  python -m src.examples.mcp_client agent1q... airbnb_search '{\"location\":\"San Francisco\"}'")
        sys.exit(1)

    target_address = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "Hello from MCP Client!"
    
    # Parse arguments if provided for tool calls
    args = {}
    if len(sys.argv) > 3:
        try:
            args = json.loads(sys.argv[3])
        except json.JSONDecodeError:
            print(f"Error: Arguments must be valid JSON")
            sys.exit(1)

    # Create a persistent agent
    client_agent = Agent(
        name="mcp_client",
        port=8001,
        endpoint=["http://127.0.0.1:8001"],
        mailbox=False
    )
    
    # Determine which protocol to use based on the command
    use_mcp_protocol = command.lower() == "list" or command in ["airbnb_search", "airbnb_listing_details"]
    
    if use_mcp_protocol:
        # Use MCP protocol for tool operations
        client_agent.include(mcp_protocol, publish_manifest=True)
    else:
        # Use Chat protocol for regular messages
        chat_proto = Protocol(spec=chat_protocol_spec)
        client_agent.include(chat_proto, publish_manifest=True)
        
        # Define chat protocol handlers
        @chat_proto.on_message(ChatMessage)
        async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
            for item in msg.content:
                if isinstance(item, TextContent):
                    ctx.logger.info(f"Received message from {sender}: {item.text}")
                    print(f"Received message from {sender}: {item.text}")
                    # Send acknowledgment
                    ack = ChatAcknowledgement(
                        timestamp=datetime.utcnow(),
                        acknowledged_msg_id=msg.msg_id
                    )
                    await ctx.send(sender, ack)

        @chat_proto.on_message(ChatAcknowledgement)
        async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
            ctx.logger.info(f"Received acknowledgement from {sender} for message: {msg.acknowledged_msg_id}")
            print(f"Received acknowledgement from {sender} for message: {msg.acknowledged_msg_id}")
    
    # Set up handlers for MCP protocol responses
    @client_agent.on_message(MCPListToolsResponse)
    async def handle_list_tools_response(ctx: Context, sender: str, msg: MCPListToolsResponse):
        print(f"\nFound {len(msg.tools)} tools:")
        for tool in msg.tools:
            print(f"\n- {tool.name}")
            print(f"  Description: {tool.description}")
            print(f"  Schema: {json.dumps(tool.inputSchema, indent=2)}")
    
    @client_agent.on_message(MCPCallToolResponse)
    async def handle_call_tool_response(ctx: Context, sender: str, msg: MCPCallToolResponse):
        if msg.error:
            print(f"Error: {msg.error}")
        else:
            # Try to parse as JSON for pretty printing
            try:
                parsed_content = json.loads(msg.content)
                print(json.dumps(parsed_content, indent=2))
            except:
                # Just print as string
                print(msg.content)

    @client_agent.on_event("startup")
    async def startup_handler(ctx: Context):
        ctx.logger.info(f"[mcp_client] My address is {ctx.agent.address}")
        
        # Determine what type of message to send based on the command
        if command.lower() == "list":
            # Send list tools request
            ctx.logger.info(f"[mcp_client] Requesting tool list from {target_address}")
            await ctx.send(target_address, MCPListToolsRequest())
        elif command in ["airbnb_search", "airbnb_listing_details"]:
            # Send tool call request
            ctx.logger.info(f"[mcp_client] Calling tool {command} on {target_address} with args: {args}")
            await ctx.send(
                target_address, 
                MCPCallToolRequest(
                    tool=command,
                    args=args
                )
            )
        else:
            # Send regular chat message
            ctx.logger.info(f"[mcp_client] Sending ChatMessage to {target_address}")
            msg = ChatMessage(
                timestamp=datetime.utcnow(),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=command)]
            )
            await ctx.send(target_address, msg)

    # Run the client
    client_agent.run()