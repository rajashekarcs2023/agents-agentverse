#!/usr/bin/env python3
# src/examples/mcp_tool_client.py

import sys
import os
import json
import logging
import asyncio
from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Protocol

# Add parent directory to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import MCP protocol models for tool listing and calling
from mcp_protocol import (
    MCPListToolsRequest,
    MCPListToolsResponse,
    MCPCallToolRequest,
    MCPCallToolResponse,
    mcp_protocol
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_tool_client")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.examples.mcp_tool_client <server_address> [command] [arguments_json]")
        print("\nCommands:")
        print("  list - List available tools")
        print("  <tool_name> - Call a specific tool with arguments")
        print("\nExamples:")
        print("  python -m src.examples.mcp_tool_client agent1q... list")
        print("  python -m src.examples.mcp_tool_client agent1q... airbnb_search '{\"location\":\"San Francisco\"}'")
        sys.exit(1)

    server_address = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "list"
    
    # Parse arguments if provided
    args = {}
    if len(sys.argv) > 3:
        try:
            args = json.loads(sys.argv[3])
        except json.JSONDecodeError:
            print(f"Error: Arguments must be valid JSON")
            sys.exit(1)

    # Create client agent
    client_agent = Agent(
        name="mcp_tool_client",
        port=8001,
        endpoint=["http://127.0.0.1:8001"],  # Use 127.0.0.1 instead of localhost
        mailbox=False  # Disable mailbox to avoid connection issues
    )
    
    # Include the MCP protocol
    client_agent.include(mcp_protocol, publish_manifest=True)

    # Set up response handlers
    @client_agent.on_message(MCPListToolsResponse)
    async def handle_list_tools_response(ctx: Context, sender: str, msg: MCPListToolsResponse):
        print(f"\nFound {len(msg.tools)} tools:")
        for tool in msg.tools:
            print(f"\n- {tool.name}")
            print(f"  Description: {tool.description}")
            print(f"  Schema: {json.dumps(tool.inputSchema, indent=2)}")
        
        # Exit after receiving response
        ctx.logger.info("Received tool list, shutting down")
        await ctx.stop()

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
        
        # Exit after receiving response
        ctx.logger.info("Received tool response, shutting down")
        await ctx.stop()

    @client_agent.on_event("startup")
    async def startup_handler(ctx: Context):
        ctx.logger.info(f"[mcp_tool_client] My address is {ctx.agent.address}")
        
        # Wait a bit to ensure the server is fully initialized
        await asyncio.sleep(2)
        
        if command.lower() == "list":
            # Send list tools request
            ctx.logger.info(f"[mcp_tool_client] Requesting tool list from {server_address}")
            await ctx.send(server_address, MCPListToolsRequest())
            
            # Set a timeout in case we don't receive a response
            asyncio.create_task(timeout_handler(ctx, 30))
        else:
            # Send tool call request
            ctx.logger.info(f"[mcp_tool_client] Calling tool {command} on {server_address} with args: {args}")
            await ctx.send(
                server_address, 
                MCPCallToolRequest(
                    tool=command,
                    args=args
                )
            )
            
            # Set a timeout in case we don't receive a response
            asyncio.create_task(timeout_handler(ctx, 30))

    # Define a timeout handler to exit if no response is received
    async def timeout_handler(ctx, seconds):
        await asyncio.sleep(seconds)
        print(f"\nNo response received after {seconds} seconds. The server might be busy or unable to respond.")
        print("If you're trying to list tools, the server might not support the listTools method.")
        print("Check the server logs for more information.")
        await ctx.stop()
    
    # Run the client agent
    client_agent.run()
