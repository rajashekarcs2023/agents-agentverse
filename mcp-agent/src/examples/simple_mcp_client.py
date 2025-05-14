#!/usr/bin/env python3
# src/examples/simple_mcp_client.py
# A simplified MCP client that just prints the known Airbnb tools

import sys
import os
import json
import logging

# Add parent directory to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("simple_mcp_client")

def main():
    # Print the hardcoded Airbnb tools that we know are available
    print("\nAirbnb MCP Tools:")
    
    # Tool 1: airbnb_search
    print("\n- airbnb_search")
    print("  Description: Search for Airbnb listings")
    print("  Schema: {")
    print("    \"type\": \"object\",")
    print("    \"properties\": {")
    print("      \"location\": {")
    print("        \"type\": \"string\",")
    print("        \"description\": \"Location to search for\"")
    print("      }")
    print("    },")
    print("    \"required\": [\"location\"]")
    print("  }")
    
    # Tool 2: airbnb_listing_details
    print("\n- airbnb_listing_details")
    print("  Description: Get detailed information about a specific Airbnb listing")
    print("  Schema: {")
    print("    \"type\": \"object\",")
    print("    \"properties\": {")
    print("      \"id\": {")
    print("        \"type\": \"string\",")
    print("        \"description\": \"Listing ID\"")
    print("      }")
    print("    },")
    print("    \"required\": [\"id\"]")
    print("  }")
    
    print("\nTo use these tools with the MCP client:")
    print("  python -m src.examples.mcp_client agent1qdd934a5fsm4uvx0gtyndajjjyl7vt3x3cnzwh6mnvka3p7x0m2hwqf3spk airbnb_search '{\"location\":\"San Francisco\"}'")

if __name__ == "__main__":
    main()
