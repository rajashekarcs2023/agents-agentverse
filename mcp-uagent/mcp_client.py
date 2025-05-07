# mcp_client.py
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from anthropic import Anthropic
from typing import Dict, List, Any, Optional
from uagents import Model, Field
import asyncio
import logging
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_client")

class MCPServerInfo(Model):
    """Information about an MCP server"""
    server_id: str = Field(description="Unique identifier for the MCP server")
    server_path: str = Field(description="Path to the MCP server script or command")
    description: str = Field(description="Human-readable description of the server's functionality")
    is_npx: bool = Field(description="Whether this is an NPX-based server", default=False)
    npx_package: str = Field(description="NPX package name if is_npx is true", default="")
    env_vars: Dict[str, str] = Field(description="Environment variables for the server", default={})
    extra_args: List[str] = Field(description="Additional arguments for the server", default=[])

class MCPProcessRequest(Model):
    """Request to process a query through MCP servers"""
    query: str = Field(description="Natural language query to process")

class MCPProcessResponse(Model):
    """Response from processing a query through MCP servers"""
    results: str = Field(description="Results from processing the query")

class MCPClientManager:
    """Manager for MCP client connections to multiple servers"""
    
    def __init__(self, anthropic_api_key=None):
        """Initialize the MCP client manager"""
        self.exit_stack = AsyncExitStack()
        self.servers = {}  # Dictionary to store server info
        self.anthropic = Anthropic(api_key=anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"))
    
    async def connect_server(self, server_info: MCPServerInfo) -> bool:
        """Connect to an MCP server and register its tools
        
        Args:
            server_info: Information about the server to connect to
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Check if already connected
            if server_info.server_id in self.servers:
                logger.info(f"Server {server_info.server_id} already connected")
                return True
            
            # Configure server connection
            if server_info.is_npx:
                # Handle NPX-based servers
                command = "npx"
                args = ["-y"]
                if server_info.npx_package:
                    args.append(server_info.npx_package)
                # Add any extra args
                args.extend(server_info.extra_args)
            else:
                # Handle file-based servers
                is_python = server_info.server_path.endswith('.py')
                is_js = server_info.server_path.endswith('.js')
                if not (is_python or is_js):
                    logger.error(f"Server script must be a .py or .js file: {server_info.server_path}")
                    return False
                
                command = "python" if is_python else "node"
                args = [server_info.server_path]
            
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=server_info.env_vars
            )
            
            logger.info(f"Connecting to {server_info.server_id} with command: {command} {' '.join(args)}")
            
            # Connect to server
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()
            
            # Get available tools
            response = await session.list_tools()
            tools = response.tools
            tool_names = [tool.name for tool in tools]
            logger.info(f"Connected to server {server_info.server_id} with tools: {tool_names}")
            
            # Store server info
            self.servers[server_info.server_id] = {
                "session": session,
                "tools": tools,
                "info": server_info
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to server {server_info.server_id}: {str(e)}")
            return False
    
    async def process_query(self, query: str) -> str:
        """Process a natural language query using Claude to select tools
        
        Args:
            query: Natural language query from user
            
        Returns:
            str: Results from processing the query
        """
        if not self.servers:
            return "No MCP servers connected. Please connect at least one server first."
        
        # Gather all available tools from all servers
        all_tools = []
        for server_id, server_info in self.servers.items():
            for tool in server_info["tools"]:
                # Format tool with server prefix
                tool_name = f"{server_id}.{tool.name}"
                all_tools.append({
                    "name": tool_name,
                    "description": f"[{server_id}] {tool.description}",
                    "input_schema": tool.inputSchema,
                    "server_id": server_id,
                    "tool_name": tool.name
                })
        
        # Format tools for Claude
        tools_for_claude = []
        for tool in all_tools:
            tools_for_claude.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"]
            })
        
        # Call Claude to select tool and extract parameters
        messages = [{"role": "user", "content": query}]
        
        try:
            # Make initial request to Claude
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=messages,
                tools=tools_for_claude
            )
            
            # Process the response
            result_parts = []
            
            for content in response.content:
                if content.type == 'text':
                    result_parts.append(content.text)
                elif content.type == 'tool_use':
                    full_name = content.name
                    tool_args = content.input
                    
                    # Extract server_id and tool_name
                    server_id, tool_name = full_name.split(".", 1)
                    
                    result_parts.append(f"\n[Using tool: {tool_name} from {server_id}]\n")
                    
                    # Call the tool on the appropriate server
                    if server_id in self.servers:
                        session = self.servers[server_id]["session"]
                        try:
                            result = await session.call_tool(tool_name, tool_args)
                            
                            # Format the result nicely
                            if isinstance(result.content, str):
                                formatted_result = result.content
                            else:
                                # Try to format JSON nicely
                                try:
                                    if isinstance(result.content, dict) or isinstance(result.content, list):
                                        formatted_result = json.dumps(result.content, indent=2)
                                    else:
                                        formatted_result = str(result.content)
                                except:
                                    formatted_result = str(result.content)
                            
                            result_parts.append(formatted_result)
                            
                            # Add tool result to messages for follow-up
                            if hasattr(content, 'text') and content.text:
                                messages.append({"role": "assistant", "content": content.text})
                            
                            # Limit the response size for Claude
                            if len(formatted_result) > 2000:
                                concise_result = formatted_result[:2000] + "... [truncated for brevity]"
                            else:
                                concise_result = formatted_result
                                
                            messages.append({"role": "user", "content": 
                                            f"Result from {tool_name}:\n{concise_result}"})
                            
                            # Get follow-up response from Claude
                            follow_up = self.anthropic.messages.create(
                                model="claude-3-5-sonnet-20241022",
                                max_tokens=1000,
                                messages=messages,
                            )
                            
                            # Add follow-up response
                            if follow_up.content:
                                result_parts.append("\n" + follow_up.content[0].text)
                                
                        except Exception as e:
                            error_msg = f"Error calling tool {tool_name}: {str(e)}"
                            result_parts.append(error_msg)
                    else:
                        result_parts.append(f"Error: Server {server_id} not found")
            
            return "\n".join(result_parts)
            
        except Exception as e:
            logger.error(f"Error processing query with Claude: {str(e)}")
            return f"Error processing your request: {str(e)}"
    
    async def get_connected_servers(self) -> List[MCPServerInfo]:
        """Get information about all connected servers
        
        Returns:
            List[MCPServerInfo]: List of connected server information
        """
        return [server["info"] for server in self.servers.values()]
    
    async def cleanup(self):
        """Clean up all resources when shutting down"""
        await self.exit_stack.aclose()