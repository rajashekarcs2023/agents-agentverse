"""
MCP uAgent Adapter

This module provides a clean adapter for integrating any MCP server with the uAgents framework.
It allows easy registration of MCP servers as uAgents on the agentverse platform.
"""

import os
import sys
import json
import asyncio
import logging
import subprocess
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass

from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from pydantic import Field, BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_uagent_adapter")

class MCPToolParameter(BaseModel):
    """Model for MCP tool parameter"""
    name: str
    description: str
    type: str
    required: bool = False

class MCPTool(BaseModel):
    """Model for MCP tool"""
    name: str
    description: str
    parameters: List[MCPToolParameter]

class MCPRequest(Model):
    """Model for MCP request message"""
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

class MCPResponse(Model):
    """Model for MCP response message"""
    success: bool
    result: Any
    error: Optional[str] = None

class MCPUAgentAdapter:
    """
    Adapter for integrating MCP servers with uAgents.
    
    This class provides a clean interface for registering any MCP server as a uAgent
    on the agentverse platform.
    """
    
    def __init__(
        self,
        name: str,
        command: str,
        args: List[str] = None,
        env: Dict[str, str] = None,
        port: int = 8000,
        mailbox: bool = True,
        cwd: str = None
    ):
        """
        Initialize the MCP uAgent Adapter.
        
        Args:
            name: Name of the MCP server
            command: Command to start the MCP server
            args: Arguments for the MCP server command
            env: Environment variables for the MCP server
            port: Port for the uAgent to listen on
            mailbox: Whether to enable the mailbox for the uAgent
            cwd: Current working directory for the MCP server process
        """
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd or os.getcwd()
        
        # Create the uAgent
        self.agent = Agent(
            name=f"{name.lower()}_mcp_agent",
            port=port,
            mailbox=mailbox
        )
        
        # Set up rate limiting protocol
        self.protocol = QuotaProtocol(
            storage_reference=self.agent.storage,
            name=f"{name}-Protocol",
            version="0.1.0",
            default_rate_limit=RateLimit(window_size_minutes=60, max_requests=100),
        )
        
        # MCP server process
        self.mcp_process = None
        self.is_running = False
        
        # Cache for available tools
        self.tools_cache = None
        
        # Set up message handlers
        self._setup_message_handlers()
    
    def _setup_message_handlers(self):
        """Set up message handlers for the uAgent"""
        
        @self.protocol.on_message(MCPRequest, replies={MCPResponse})
        async def handle_mcp_request(ctx: Context, sender: str, msg: MCPRequest):
            """Handle MCP request message"""
            ctx.logger.info(f"Received request for tool: {msg.tool_name}")
            
            try:
                # Ensure MCP server is running
                if not self.is_running:
                    await self._start_mcp_server()
                
                # Call the MCP tool
                result = await self._call_mcp_tool(msg.tool_name, msg.parameters)
                
                # Send the response
                await ctx.send(
                    sender,
                    MCPResponse(success=True, result=result)
                )
                
            except Exception as e:
                ctx.logger.error(f"Error handling MCP request: {e}")
                await ctx.send(
                    sender,
                    MCPResponse(success=False, result=None, error=str(e))
                )
    
    async def _start_mcp_server(self) -> bool:
        """Start the MCP server process"""
        logger.info(f"Starting {self.name} MCP server: {self.command} {' '.join(self.args)}")
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.env)
            
            # Start the process
            self.mcp_process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
                cwd=self.cwd
            )
            
            # Wait for startup
            await asyncio.sleep(2)
            
            # Check if process is still running
            if self.mcp_process.poll() is not None:
                logger.error(f"MCP server process exited with code {self.mcp_process.poll()}")
                return False
            
            self.is_running = True
            logger.info(f"{self.name} MCP server started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {self.name} MCP server: {e}")
            return False
    
    async def _call_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Call an MCP tool with the given parameters.
        
        This method should be implemented by subclasses to handle the specific
        communication protocol with the MCP server.
        """
        raise NotImplementedError("Subclasses must implement _call_mcp_tool")
    
    async def _get_mcp_tools(self) -> List[MCPTool]:
        """
        Get the list of available tools from the MCP server.
        
        This method should be implemented by subclasses to handle the specific
        communication protocol with the MCP server.
        """
        raise NotImplementedError("Subclasses must implement _get_mcp_tools")
    
    def cleanup(self):
        """Clean up resources"""
        # Clean up MCP process if it exists
        if self.mcp_process:
            try:
                logger.info(f"Terminating {self.name} MCP server process")
                self.mcp_process.terminate()
                self.mcp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"{self.name} MCP server did not terminate gracefully, killing")
                self.mcp_process.kill()
            except Exception as e:
                logger.error(f"Error cleaning up MCP process: {e}")
        
        self.is_running = False
    
    def run(self):
        """Run the uAgent"""
        # Set up startup handler
        @self.agent.on_event("startup")
        async def on_startup(ctx: Context):
            """Start the MCP server on startup"""
            ctx.logger.info(f"Starting {self.name} MCP server on startup")
            success = await self._start_mcp_server()
            if success:
                ctx.logger.info(f"Successfully started {self.name} MCP server")
                
                # Get available tools
                try:
                    tools = await self._get_mcp_tools()
                    self.tools_cache = tools
                    ctx.logger.info(f"Available tools: {[tool.name for tool in tools]}")
                except Exception as e:
                    ctx.logger.error(f"Error getting available tools: {e}")
            else:
                ctx.logger.error(f"Failed to start {self.name} MCP server")
        
        # Set up shutdown handler
        @self.agent.on_event("shutdown")
        async def on_shutdown(ctx: Context):
            """Clean up on shutdown"""
            ctx.logger.info(f"Shutting down {self.name} MCP server")
            self.cleanup()
        
        # Include the protocol
        self.agent.include(self.protocol, publish_manifest=True)
        
        # Run the agent
        logger.info(f"Running {self.name} MCP uAgent on address: {self.agent.address}")
        self.agent.run()
