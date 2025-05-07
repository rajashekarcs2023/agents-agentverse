# mcp_client.py
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, Any, Optional
from uagents import Model, Field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_client")

# Global variable to store MCP session
mcp_session = None
mcp_exit_stack = None

async def connect_to_food_mcp():
    """Connect to the Food MCP server"""
    global mcp_session, mcp_exit_stack
    
    mcp_exit_stack = AsyncExitStack()
    
    try:
        logger.info("Connecting to Food MCP server")
        
        # Configure the MCP server connection
        server_params = StdioServerParameters(
            command="python",
            args=["food_mcp_server.py"],
            env={}
        )
        
        # Connect to the server
        stdio_transport = await mcp_exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        mcp_session = await mcp_exit_stack.enter_async_context(ClientSession(stdio, write))
        
        # Initialize the session
        await mcp_session.initialize()
        
        # Get available tools to verify connection
        response = await mcp_session.list_tools()
        tools = response.tools
        
        logger.info(f"Connected to Food MCP server with tools: {[tool.name for tool in tools]}")
        return True
        
    except Exception as e:
        if mcp_exit_stack:
            await mcp_exit_stack.aclose()
        logger.error(f"Error connecting to Food MCP server: {str(e)}")
        return False

async def search_food_products(query: str) -> str:
    """Search for food products
    
    Args:
        query: Search query
        
    Returns:
        Search results as a string
    """
    global mcp_session
    
    if not mcp_session:
        return "Error: Not connected to Food MCP server"
    
    try:
        result = await mcp_session.call_tool("search_products", {"query": query})
        return result.content
    except Exception as e:
        error_msg = f"Error searching for food products: {str(e)}"
        logger.error(error_msg)
        return error_msg

async def get_nutrition_facts(product_name: str) -> str:
    """Get nutrition facts for a food product
    
    Args:
        product_name: Name of the food product
        
    Returns:
        Nutrition facts as a string
    """
    global mcp_session
    
    if not mcp_session:
        return "Error: Not connected to Food MCP server"
    
    try:
        result = await mcp_session.call_tool("get_nutrition_facts", {"product_name": product_name})
        return result.content
    except Exception as e:
        error_msg = f"Error getting nutrition facts: {str(e)}"
        logger.error(error_msg)
        return error_msg

async def analyze_ingredients(product_name: str) -> str:
    """Analyze ingredients in a food product
    
    Args:
        product_name: Name of the food product
        
    Returns:
        Ingredient analysis as a string
    """
    global mcp_session
    
    if not mcp_session:
        return "Error: Not connected to Food MCP server"
    
    try:
        result = await mcp_session.call_tool("analyze_ingredients", {"product_name": product_name})
        return result.content
    except Exception as e:
        error_msg = f"Error analyzing ingredients: {str(e)}"
        logger.error(error_msg)
        return error_msg

async def cleanup_mcp_connection():
    """Clean up MCP connection"""
    global mcp_session, mcp_exit_stack
    
    if mcp_exit_stack:
        try:
            await mcp_exit_stack.aclose()
            logger.info("MCP connection closed")
        except Exception as e:
            logger.error(f"Error closing MCP connection: {str(e)}")
    
    mcp_session = None
    mcp_exit_stack = None