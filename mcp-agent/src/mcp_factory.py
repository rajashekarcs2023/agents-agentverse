# src/mcp_factory.py
import sys
import json
import logging
import os
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Add parent directory to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from mcp_server_adapter import MCPServerAdapter

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_factory")

def create_mcp_server_agent(
    name: str,
    command: str,
    args: List[str] = None,
    env: Dict[str, str] = None,
    port: int = 8000
) -> MCPServerAdapter:
    """
    Create an MCP server agent for any MCP server
    
    Args:
        name: Name of the MCP server
        command: Command to start the MCP server
        args: Arguments for the MCP server command
        env: Environment variables for the MCP server
        port: Port for the agent to listen on
        
    Returns:
        An MCPServerAdapter instance
    """
    return MCPServerAdapter(
        name=name,
        command=command,
        args=args or [],
        env=env or {},
        port=port
    )

def get_server_configs() -> Dict[str, Dict[str, Any]]:
    """Get predefined server configurations"""
    return {
        "airbnb": {
            "name": "airbnb",
            "command": "npx",
            "args": ["-y", "@openbnb/mcp-server-airbnb"],
            "env": {},
            "description": "Airbnb MCP server for searching listings and getting details"
        },
        "tavily": {
            "name": "tavily",
            "command": "npx",
            "args": ["-y", "tavily-mcp"],
            "env": {"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
            "requires_api_key": True,
            "description": "Tavily MCP server for web search and extraction"
        },
        "neo4j": {
            "name": "neo4j",
            "command": "npx",
            "args": ["-y", "neo4j-mcp"],
            "env": {
                "NEO4J_URI": os.getenv("NEO4J_URI", ""),
                "NEO4J_USERNAME": os.getenv("NEO4J_USERNAME", ""),
                "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", "")
            },
            "requires_api_key": True,
            "description": "Neo4j MCP server for graph database operations"
        }
    }

if __name__ == "__main__":
    # Get predefined server configs
    server_configs = get_server_configs()
    
    # Get port from arguments
    port = 8000
    for arg in sys.argv:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
            except:
                pass
    
    # Process command-line arguments
    if len(sys.argv) > 1:
        # Check if it's a JSON config file
        if sys.argv[1].endswith(".json"):
            config_file = sys.argv[1]
            
            try:
                # Load config from file
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Add port if specified
                config["port"] = port
                
                # Create and run the adapter
                adapter = create_mcp_server_agent(**config)
                adapter.run()
                
            except Exception as e:
                logger.error(f"Error creating MCP server agent: {e}")
                sys.exit(1)
        
        # Check if it's a predefined server
        elif sys.argv[1].startswith("--") and sys.argv[1][2:] in server_configs:
            server_type = sys.argv[1][2:]
            server_config = server_configs[server_type].copy()
            
            # Check if API key is required but not provided
            if server_config.get("requires_api_key", False):
                api_key_env = f"{server_type.upper()}_API_KEY"
                api_key = os.getenv(api_key_env)
                
                if not api_key and len(sys.argv) > 2:
                    # Try to get API key from command line
                    api_key = sys.argv[2]
                    server_config["env"][f"{server_type.upper()}_API_KEY"] = api_key
                    
                if not api_key:
                    logger.error(f"API key required for {server_type} MCP server.")
                    logger.error(f"Set {api_key_env} environment variable or provide it as an argument.")
                    sys.exit(1)
            
            # Handle special arguments
            if server_type == "airbnb" and "--ignore-robots-txt" in sys.argv:
                server_config["args"].append("--ignore-robots-txt")
            
            # Set port
            server_config["port"] = port
            
            # Remove extra keys not used by the adapter
            for key in ["requires_api_key", "description"]:
                if key in server_config:
                    del server_config[key]
            
            # Create and run the adapter
            print(f"Starting {server_type} MCP server agent on port {port}")
            adapter = create_mcp_server_agent(**server_config)
            adapter.run()
            
        else:
            # Print usage
            print("Usage:")
            print("  python -m src.mcp_factory <config_file.json>")
            print("  python -m src.mcp_factory --<server_type> [API_KEY] [--port=PORT]")
            print("\nAvailable server types:")
            
            for server_type, config in server_configs.items():
                api_key_info = " (requires API key)" if config.get("requires_api_key", False) else ""
                print(f"  {server_type}: {config['description']}{api_key_info}")
            
            print("\nExample config.json:")
            print(json.dumps({
                "name": "example",
                "command": "npx",
                "args": ["-y", "example-mcp-server"],
                "env": {"API_KEY": "your-api-key"},
                "port": 8000
            }, indent=2))
    else:
        # No arguments provided, print usage
        print("MCP Server Factory")
        print("=================")
        print("This tool creates MCP server agents for Agentverse.")
        print("\nUsage:")
        print("  python -m src.mcp_factory <config_file.json>")
        print("  python -m src.mcp_factory --<server_type> [API_KEY] [--port=PORT]")
        print("\nExample:")
        print("  python -m src.mcp_factory --airbnb [--ignore-robots-txt] [--port=8000]")
        print("  python -m src.mcp_factory --tavily YOUR_TAVILY_API_KEY [--port=8000]")