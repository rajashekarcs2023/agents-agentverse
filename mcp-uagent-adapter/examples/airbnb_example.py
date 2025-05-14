"""
Airbnb MCP uAgent Example

This example demonstrates how to use the Airbnb MCP uAgent adapter to register
an Airbnb MCP server as a uAgent on the agentverse platform and how to interact
with it using the MCP uAgent client.
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from typing import Dict, Any

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.airbnb_mcp_adapter import AirbnbMCPAdapter
from src.mcp_uagent_client import MCPUAgentClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("airbnb_example")

# Parse command line arguments
parser = argparse.ArgumentParser(description='Airbnb MCP uAgent Example')
parser.add_argument('--server-port', type=int, default=8000, help='Port for the server uAgent')
parser.add_argument('--client-port', type=int, default=8001, help='Port for the client uAgent')
parser.add_argument('--mode', choices=['server', 'client', 'both'], default='both', help='Mode to run in')
args = parser.parse_args()

# Global variables
server_address = None

async def run_server():
    """Run the Airbnb MCP uAgent server"""
    global server_address
    
    logger.info("Starting Airbnb MCP uAgent server")
    
    # Create the adapter
    adapter = AirbnbMCPAdapter(
        port=args.server_port,
        mailbox=True,
        cwd=os.getcwd()
    )
    
    # Store the server address
    server_address = adapter.agent.address
    
    # Write the server address to a file for the client to use
    with open("server_address.txt", "w") as f:
        f.write(server_address)
    
    logger.info(f"Airbnb MCP uAgent server address: {server_address}")
    
    try:
        # Run the adapter
        adapter.run()
    except KeyboardInterrupt:
        logger.info("Shutting down Airbnb MCP uAgent server")
        adapter.cleanup()

async def run_client():
    """Run the Airbnb MCP uAgent client"""
    global server_address
    
    logger.info("Starting Airbnb MCP uAgent client")
    
    # If server_address is not set, try to read it from the file
    if not server_address:
        try:
            with open("server_address.txt", "r") as f:
                server_address = f.read().strip()
        except FileNotFoundError:
            logger.error("Server address file not found. Please run the server first.")
            return
    
    logger.info(f"Connecting to Airbnb MCP uAgent server at: {server_address}")
    
    # Create the client
    client = MCPUAgentClient(
        name="airbnb_client",
        target_address=server_address,
        port=args.client_port,
        mailbox=True
    )
    
    # Start the client in a separate thread
    import threading
    client_thread = threading.Thread(target=client.run, daemon=True)
    client_thread.start()
    
    # Wait for the client to start
    await asyncio.sleep(2)
    
    try:
        # Search for listings in San Francisco
        logger.info("Searching for listings in San Francisco")
        search_result = await client.call_tool(
            "airbnb_search",
            {
                "location": "San Francisco",
                "checkin": "2025-06-01",
                "checkout": "2025-06-07",
                "adults": 2,
                "limit": 5
            }
        )
        
        # Print the search results
        logger.info(f"Search results: {json.dumps(search_result, indent=2)}")
        
        # If we have listings, get details for the first one
        if search_result and "listings" in search_result and search_result["listings"]:
            first_listing = search_result["listings"][0]
            listing_id = first_listing.get("id")
            
            if listing_id:
                logger.info(f"Getting details for listing {listing_id}")
                listing_details = await client.call_tool(
                    "airbnb_listing_details",
                    {"listing_id": listing_id}
                )
                
                logger.info(f"Listing details: {json.dumps(listing_details, indent=2)}")
        
    except Exception as e:
        logger.error(f"Error in client: {e}")
    
    finally:
        # Keep the client running for a while to allow for responses
        await asyncio.sleep(5)
        logger.info("Client example completed")

async def main():
    """Main function"""
    if args.mode == 'server':
        await run_server()
    elif args.mode == 'client':
        await run_client()
    elif args.mode == 'both':
        # Run server in a separate process
        import multiprocessing
        server_process = multiprocessing.Process(target=asyncio.run, args=(run_server(),))
        server_process.start()
        
        # Wait for the server to start
        await asyncio.sleep(5)
        
        # Run client
        await run_client()
        
        # Wait for the client to finish
        await asyncio.sleep(5)
        
        # Terminate the server process
        server_process.terminate()
        server_process.join()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
