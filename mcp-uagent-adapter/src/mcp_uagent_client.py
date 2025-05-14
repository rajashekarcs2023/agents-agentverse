"""
MCP uAgent Client

This module provides a client for interacting with MCP uAgents on the agentverse platform.
It handles communication with the uAgent and provides a simple interface for calling MCP tools.
"""

import os
import json
import asyncio
import logging
import uuid
from typing import Dict, List, Any, Optional

from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol
from mcp_uagent_adapter import MCPRequest, MCPResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_uagent_client")

class MCPUAgentClient:
    """
    Client for interacting with MCP uAgents on the agentverse platform.
    
    This class provides a simple interface for calling MCP tools and handles
    communication with the uAgent.
    """
    
    def __init__(
        self,
        name: str,
        target_address: str,
        port: int = 8001,
        mailbox: bool = True
    ):
        """
        Initialize the MCP uAgent Client.
        
        Args:
            name: Name of the client
            target_address: Address of the target MCP uAgent
            port: Port for the client uAgent to listen on
            mailbox: Whether to enable the mailbox for the client uAgent
        """
        self.name = name
        self.target_address = target_address
        
        # Create the client uAgent
        self.agent = Agent(
            name=f"{name.lower()}_client",
            port=port,
            mailbox=mailbox
        )
        
        # Set up protocol
        self.protocol = QuotaProtocol(
            storage_reference=self.agent.storage,
            name=f"{name}-Client-Protocol",
            version="0.1.0"
        )
        
        # Request futures
        self.request_futures = {}
        
        # Set up message handlers
        self._setup_message_handlers()
    
    def _setup_message_handlers(self):
        """Set up message handlers for the client uAgent"""
        
        @self.protocol.on_message(MCPResponse)
        async def handle_mcp_response(ctx: Context, sender: str, msg: MCPResponse):
            """Handle MCP response message"""
            ctx.logger.info(f"Received response from {sender}")
            
            # Get the request ID from the sender (last part of the address)
            request_id = sender.split(".")[-1]
            
            # Resolve the future if it exists
            if request_id in self.request_futures:
                future = self.request_futures.pop(request_id)
                future.set_result(msg)
            else:
                ctx.logger.warning(f"Received response for unknown request ID: {request_id}")
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any] = None) -> Any:
        """
        Call an MCP tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to call
            parameters: Parameters for the tool
            
        Returns:
            The result of the tool call
        """
        logger.info(f"Calling MCP tool: {tool_name} with parameters: {parameters or {}}")
        
        # Create a future to wait for the response
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Store the future
        self.request_futures[request_id] = future
        
        # Create the request
        request = MCPRequest(
            tool_name=tool_name,
            parameters=parameters or {}
        )
        
        # Send the request
        await self.agent.context.send(
            self.target_address,
            request,
            request_id=request_id
        )
        
        # Wait for the response
        try:
            response = await asyncio.wait_for(future, timeout=30)
            
            # Check for errors
            if not response.success:
                logger.error(f"Error from MCP uAgent: {response.error}")
                raise Exception(f"MCP uAgent error: {response.error}")
            
            # Return the result
            return response.result
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for response from MCP uAgent")
            raise Exception("Timeout waiting for response from MCP uAgent")
        
        finally:
            # Clean up the future if it's still in the dictionary
            if request_id in self.request_futures:
                self.request_futures.pop(request_id)
    
    def run(self):
        """Run the client uAgent"""
        # Include the protocol
        self.agent.include(self.protocol, publish_manifest=True)
        
        # Run the agent
        logger.info(f"Running {self.name} MCP uAgent Client on address: {self.agent.address}")
        logger.info(f"Target MCP uAgent address: {self.target_address}")
        self.agent.run()


# HTTP Server for UI interaction
class MCPUAgentHTTPServer:
    """
    HTTP Server for UI interaction with MCP uAgents.
    
    This class provides a simple HTTP server that allows UI applications to
    interact with MCP uAgents through HTTP GET/POST requests.
    """
    
    def __init__(
        self,
        client: MCPUAgentClient,
        host: str = "localhost",
        port: int = 8080
    ):
        """
        Initialize the MCP uAgent HTTP Server.
        
        Args:
            client: MCP uAgent Client to use for communication
            host: Host to bind the HTTP server to
            port: Port to bind the HTTP server to
        """
        self.client = client
        self.host = host
        self.port = port
        
        # Import web server libraries
        import aiohttp
        from aiohttp import web
        self.web = web
        
        # Create the web app
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Set up routes for the HTTP server"""
        self.app.router.add_get("/tools", self.handle_get_tools)
        self.app.router.add_post("/call", self.handle_call_tool)
    
    async def handle_get_tools(self, request):
        """Handle GET request for available tools"""
        try:
            # Call the rpc.discover tool to get available tools
            tools = await self.client.call_tool("rpc.discover")
            
            # Return the tools as JSON
            return self.web.json_response(tools)
            
        except Exception as e:
            logger.error(f"Error getting tools: {e}")
            return self.web.json_response(
                {"error": str(e)},
                status=500
            )
    
    async def handle_call_tool(self, request):
        """Handle POST request to call a tool"""
        try:
            # Parse the request body
            body = await request.json()
            
            # Extract tool name and parameters
            tool_name = body.get("tool_name")
            parameters = body.get("parameters", {})
            
            if not tool_name:
                return self.web.json_response(
                    {"error": "Missing tool_name parameter"},
                    status=400
                )
            
            # Call the tool
            result = await self.client.call_tool(tool_name, parameters)
            
            # Return the result as JSON
            return self.web.json_response({"result": result})
            
        except Exception as e:
            logger.error(f"Error calling tool: {e}")
            return self.web.json_response(
                {"error": str(e)},
                status=500
            )
    
    async def start(self):
        """Start the HTTP server"""
        logger.info(f"Starting HTTP server on {self.host}:{self.port}")
        
        # Import runner
        from aiohttp import web
        
        # Start the server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"HTTP server running on http://{self.host}:{self.port}")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    
    def run(self):
        """Run the HTTP server in the current thread"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start())
