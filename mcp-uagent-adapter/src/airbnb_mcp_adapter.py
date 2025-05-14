"""
Airbnb MCP uAgent Adapter

This module provides a specific adapter for the Airbnb MCP server.
It extends the base MCPUAgentAdapter to handle the specific communication protocol
required for the Airbnb MCP server.
"""

import os
import json
import asyncio
import logging
import traceback
from typing import Dict, List, Any, Optional

from mcp_uagent_adapter import MCPUAgentAdapter, MCPTool, MCPToolParameter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("airbnb_mcp_adapter")

class AirbnbMCPAdapter(MCPUAgentAdapter):
    """
    Adapter for the Airbnb MCP server.
    
    This class extends the base MCPUAgentAdapter to handle the specific communication
    protocol required for the Airbnb MCP server.
    """
    
    def __init__(
        self,
        port: int = 8000,
        mailbox: bool = True,
        cwd: str = None
    ):
        """
        Initialize the Airbnb MCP uAgent Adapter.
        
        Args:
            port: Port for the uAgent to listen on
            mailbox: Whether to enable the mailbox for the uAgent
            cwd: Current working directory for the MCP server process
        """
        super().__init__(
            name="airbnb",
            command="npx",
            args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
            port=port,
            mailbox=mailbox,
            cwd=cwd
        )
    
    async def _call_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Call an Airbnb MCP tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to call
            parameters: Parameters for the tool
            
        Returns:
            The result of the tool call
        """
        logger.info(f"Calling Airbnb MCP tool: {tool_name} with parameters: {parameters}")
        
        # Construct the JSON-RPC request
        request_id = 1
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": tool_name,
            "params": parameters
        }
        
        # Convert the request to JSON
        request_json = json.dumps(request) + "\n"
        
        try:
            # Send the request to the MCP server
            self.mcp_process.stdin.write(request_json)
            self.mcp_process.stdin.flush()
            
            # Read the response from the MCP server
            response_line = self.mcp_process.stdout.readline()
            
            # Parse the response
            response = json.loads(response_line)
            
            # Check for errors
            if "error" in response:
                error = response["error"]
                logger.error(f"Error from Airbnb MCP server: {error}")
                raise Exception(f"Airbnb MCP server error: {error}")
            
            # Return the result
            return response.get("result")
            
        except Exception as e:
            logger.error(f"Error calling Airbnb MCP tool: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _get_mcp_tools(self) -> List[MCPTool]:
        """
        Get the list of available tools from the Airbnb MCP server.
        
        Returns:
            List of available tools
        """
        logger.info("Getting available tools from Airbnb MCP server")
        
        try:
            # Call the rpc.discover method to get the available tools
            result = await self._call_mcp_tool("airbnb_search", {"location": "San Francisco", "limit": 1})
            
            # For now, just return a hardcoded list of tools
            # In a real implementation, we would parse the result to get the available tools
            tools = [
                MCPTool(
                    name="airbnb_search",
                    description="Search for Airbnb listings",
                    parameters=[
                        MCPToolParameter(
                            name="location",
                            description="Location to search for",
                            type="string",
                            required=True
                        ),
                        MCPToolParameter(
                            name="checkin",
                            description="Check-in date (YYYY-MM-DD)",
                            type="string",
                            required=False
                        ),
                        MCPToolParameter(
                            name="checkout",
                            description="Check-out date (YYYY-MM-DD)",
                            type="string",
                            required=False
                        ),
                        MCPToolParameter(
                            name="adults",
                            description="Number of adults",
                            type="integer",
                            required=False
                        ),
                        MCPToolParameter(
                            name="children",
                            description="Number of children",
                            type="integer",
                            required=False
                        ),
                        MCPToolParameter(
                            name="infants",
                            description="Number of infants",
                            type="integer",
                            required=False
                        ),
                        MCPToolParameter(
                            name="pets",
                            description="Number of pets",
                            type="integer",
                            required=False
                        ),
                        MCPToolParameter(
                            name="limit",
                            description="Maximum number of results",
                            type="integer",
                            required=False
                        )
                    ]
                ),
                MCPTool(
                    name="airbnb_listing_details",
                    description="Get details for an Airbnb listing",
                    parameters=[
                        MCPToolParameter(
                            name="listing_id",
                            description="ID of the listing",
                            type="string",
                            required=True
                        )
                    ]
                )
            ]
            
            return tools
            
        except Exception as e:
            logger.error(f"Error getting available tools: {e}")
            logger.error(traceback.format_exc())
            raise
