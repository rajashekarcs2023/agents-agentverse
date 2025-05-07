# test_airbnb_mcp.py
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_test")

async def test_airbnb_mcp():
    try:
        logger.info("Connecting to Airbnb MCP server")
        
        # Configure the MCP server connection using NPX
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
            env={}
        )
        
        # Connect to the server
        async with stdio_client(server_params) as (stdio, write):
            async with ClientSession(stdio, write) as session:
                # Initialize the session
                await session.initialize()
                
                # Get available tools
                response = await session.list_tools()
                tools = response.tools
                
                logger.info(f"Available tools: {[tool.name for tool in tools]}")
                
                # Test the search tool
                logger.info("Testing airbnb_search...")
                search_result = await session.call_tool("airbnb_search", {
                    "location": "San Francisco",
                    # Note: It seems the 'limit' parameter isn't working, so we'll manually limit later
                })
                
                # Handle the TextContent response format
                content = search_result.content
                if hasattr(content, '__iter__') and not isinstance(content, str):
                    # It's a list of TextContent objects
                    for item in content:
                        if hasattr(item, 'text'):
                            try:
                                parsed_content = json.loads(item.text)
                                
                                # Print a nice header for the results
                                logger.info("\n" + "="*50)
                                logger.info("AIRBNB LISTINGS IN SAN FRANCISCO")
                                logger.info("="*50)
                                
                                # Limit to first 4 listings and format nicely
                                listings = parsed_content.get("searchResults", [])[:4]
                                logger.info(f"Showing {len(listings)} out of {len(parsed_content.get('searchResults', []))} total listings\n")
                                
                                for i, listing in enumerate(listings, 1):
                                    listing_name = listing["demandStayListing"]["description"]["name"]["localizedStringWithTranslationPreference"]
                                    listing_id = listing["id"]
                                    price_info = listing["structuredDisplayPrice"]["primaryLine"]["accessibilityLabel"]
                                    rating = listing["avgRatingA11yLabel"]
                                    badges = listing["badges"] if listing["badges"] else "None"
                                    dates = listing["structuredContent"]["secondaryLine"]
                                    
                                    # Format and display the listing
                                    logger.info(f"LISTING #{i}: {listing_name}")
                                    logger.info(f"ID: {listing_id}")
                                    logger.info(f"Price: {price_info}")
                                    logger.info(f"Rating: {rating}")
                                    logger.info(f"Badge: {badges}")
                                    logger.info(f"Dates: {dates}")
                                    
                                    # Get coordinates for map reference
                                    lat = listing["demandStayListing"]["location"]["coordinate"]["latitude"]
                                    lng = listing["demandStayListing"]["location"]["coordinate"]["longitude"]
                                    logger.info(f"Location: {lat}, {lng}")
                                    
                                    logger.info("-"*50)
                                    
                                    # Get listing details for the first listing
                                    if i == 1:
                                        logger.info(f"Getting details for first listing: {listing_name}...")
                                        details_result = await session.call_tool("airbnb_listing_details", {"id": listing_id})
                                        
                                        # Process the details result
                                        details_content = details_result.content
                                        if hasattr(details_content, '__iter__') and not isinstance(details_content, str):
                                            for detail_item in details_content:
                                                if hasattr(detail_item, 'text'):
                                                    try:
                                                        details = json.loads(detail_item.text)
                                                        logger.info("\nLISTING DETAILS:")
                                                        logger.info(f"Name: {details.get('name', 'N/A')}")
                                                        logger.info(f"Type: {details.get('type', 'N/A')}")
                                                        logger.info(f"Bedrooms: {details.get('bedrooms', 'N/A')}")
                                                        logger.info(f"Bathrooms: {details.get('bathrooms', 'N/A')}")
                                                        logger.info(f"Max Guests: {details.get('maxGuests', 'N/A')}")
                                                        
                                                        # Display amenities (limited to first 5)
                                                        amenities = details.get("amenities", [])
                                                        if amenities:
                                                            logger.info("\nTop Amenities:")
                                                            for j, amenity in enumerate(amenities[:5], 1):
                                                                logger.info(f"  {j}. {amenity.get('name', 'N/A')}")
                                                        
                                                        logger.info("\nHOST INFORMATION:")
                                                        host = details.get("host", {})
                                                        logger.info(f"Host Name: {host.get('name', 'N/A')}")
                                                        logger.info(f"Host Since: {host.get('hostSince', 'N/A')}")
                                                        logger.info("-"*50)
                                                    except json.JSONDecodeError:
                                                        logger.info("Could not parse details response as JSON")
                                
                            except json.JSONDecodeError:
                                logger.info(f"Content is not valid JSON: {item.text[:200]}...")
                elif isinstance(content, str):
                    logger.info(f"Content is a string: {content[:200]}...")
                else:
                    logger.info(f"Content has unexpected format: {type(content)}")
                
                logger.info("\nTest completed successfully")
                
    except Exception as e:
        logger.error(f"Error testing Airbnb MCP server: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_airbnb_mcp())