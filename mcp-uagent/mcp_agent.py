from uagents import Agent, Context, Model
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_agent")

# Create the agent
agent = Agent(
    name="mcp_user_agent",
    port=8000
)

# Global variable to store MCP session
mcp_session = None

@agent.on_event("startup")
async def connect_to_mcp(ctx: Context):
    """Connect to MCP server on startup"""
    global mcp_session
    
    try:
        # Start the weather MCP server and connect to it
        logger.info("Connecting to Weather MCP server")
        
        # This starts the MCP server process
        server_params = StdioServerParameters(
            command="python",  # We'll use a Python-based server
            args=["weather_mcp_server.py"],  # The server file
            env={}
        )
        
        # Connect to the server
        async with stdio_client(server_params) as (stdio, write):
            async with ClientSession(stdio, write) as session:
                mcp_session = session
                
                # Initialize the session
                await mcp_session.initialize()
                
                # List available tools
                tools_response = await mcp_session.list_tools()
                
                # Log the available tools
                logger.info("Available MCP tools:")
                for tool in tools_response.tools:
                    logger.info(f"- {tool.name}: {tool.description}")
                
                # Call a tool as an example
                logger.info("Calling get_forecast tool")
                result = await mcp_session.call_tool(
                    "get_forecast", 
                    {"latitude": 37.7749, "longitude": -122.4194}
                )
                
                # Log the result
                logger.info(f"Forecast result: {result.content}")
                
                # Keep the session alive while the agent runs
                while True:
                    await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}")

if __name__ == "__main__":
    agent.run()