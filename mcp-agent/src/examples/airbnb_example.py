# src/examples/airbnb_example.py
import sys
import json
import asyncio
import logging
from typing import List, Dict, Any

# Add parent directory to path if running as script
if __name__ == "__main__":
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp_server_adapter import MCPServerAdapter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("airbnb_example")

async def search_airbnb(adapter: MCPServerAdapter, location: str, **kwargs):
    """Search for Airbnb listings in the specified location"""
    logger.info(f"Searching for Airbnb listings in {location}")
    
    # Prepare search parameters
    params = {"location": location, **kwargs}
    
    # Call the airbnb_search tool
    result = await adapter._call_mcp_tool("airbnb_search", params)
    
    # Parse and return the result
    try:
        parsed_result = json.loads(result)
        return parsed_result
    except json.JSONDecodeError:
        logger.error(f"Failed to parse search result: {result}")
        return result

async def get_listing_details(adapter: MCPServerAdapter, listing_id: str, **kwargs):
    """Get details for a specific Airbnb listing"""
    logger.info(f"Getting details for Airbnb listing {listing_id}")
    
    # Prepare parameters
    params = {"id": listing_id, **kwargs}
    
    # Call the airbnb_listing_details tool
    result = await adapter._call_mcp_tool("airbnb_listing_details", params)
    
    # Parse and return the result
    try:
        parsed_result = json.loads(result)
        return parsed_result
    except json.JSONDecodeError:
        logger.error(f"Failed to parse listing details: {result}")
        return result

async def main():
    """Main function to demonstrate Airbnb MCP server functionality"""
    # Create MCP server adapter for Airbnb
    # Always add --ignore-robots-txt flag to avoid robots.txt restrictions
    args = ["--ignore-robots-txt"]
    
    adapter = MCPServerAdapter(
        name="airbnb",
        command="npx",
        args=["-y", "@openbnb/mcp-server-airbnb"] + args,
        port=port,
        cwd=os.getcwd()
    )
    
    try:
        # Start the MCP server
        logger.info("Starting Airbnb MCP server...")
        if not await adapter._ensure_mcp_running():
            logger.error("Failed to start Airbnb MCP server")
            return
        
        # Get available tools
        logger.info("Getting available tools...")
        tools = await adapter._get_mcp_tools()
        
        # Print detailed information about available tools
        logger.info("===== AVAILABLE TOOLS =====")
        logger.info(f"Number of tools: {len(tools)}")
        
        for i, tool in enumerate(tools):
            logger.info(f"\nTool #{i+1}:")
            logger.info(f"  Name: {tool.name}")
            logger.info(f"  Description: {tool.description if hasattr(tool, 'description') else 'N/A'}")
            logger.info(f"  Parameters: {json.dumps(tool.parameters) if hasattr(tool, 'parameters') else 'N/A'}")
            
            # Try to extract any additional attributes
            for attr in dir(tool):
                if not attr.startswith('_') and attr not in ['name', 'description', 'parameters']:
                    try:
                        value = getattr(tool, attr)
                        if not callable(value):
                            logger.info(f"  {attr}: {value}")
                    except:
                        pass
        
        logger.info("============================")
        
        # Also log the raw tool objects for inspection
        try:
            logger.info(f"Raw tools data: {json.dumps([vars(tool) for tool in tools], indent=2)}")
        except:
            logger.info(f"Could not serialize raw tools data")
            
        # Log the simple list of tool names
        logger.info(f"Tool names: {[tool.name for tool in tools]}")
        
        # Search for listings in San Francisco
        logger.info("\n--- Searching for listings in San Francisco ---")
        search_results = await search_airbnb(adapter, "San Francisco", adults=2, checkin="2025-06-01", checkout="2025-06-07")
        
        # Print search results
        if isinstance(search_results, dict) and "listings" in search_results:
            logger.info(f"Found {len(search_results['listings'])} listings in San Francisco")
            
            # If we have listings, get details for the first one
            if search_results["listings"]:
                first_listing = search_results["listings"][0]
                listing_id = first_listing.get("id")
                
                if listing_id:
                    logger.info(f"\n--- Getting details for listing {listing_id} ---")
                    listing_details = await get_listing_details(adapter, listing_id)
                    logger.info(f"Listing details: {json.dumps(listing_details, indent=2)}")
        else:
            logger.info(f"Search results: {search_results}")
    
    finally:
        # Stop the MCP server
        logger.info("Stopping Airbnb MCP server...")
        
        # Just use the regular cleanup method
        adapter.cleanup()

if __name__ == "__main__":
    # Parse command line arguments
    ignore_robots = "--ignore-robots-txt" in sys.argv
    port = 8000
    
    # Parse port from command line arguments
    for arg in sys.argv:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
            except ValueError:
                logger.warning(f"Invalid port number: {arg}")
    
    # Run the main function
    asyncio.run(main())