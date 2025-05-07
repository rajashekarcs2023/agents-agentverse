# agent.py
import os
import asyncio
from enum import Enum

from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from uagents_core.models import ErrorMessage

from chat_proto import chat_proto, mcp_management_proto
from mcp_client import MCPClientManager, MCPServerInfo

# Create the MCP client manager
mcp_manager = MCPClientManager()

# Set the global reference in chat_proto
chat_proto.mcp_manager = mcp_manager
mcp_management_proto.mcp_manager = mcp_manager

# Create the agent
agent = Agent(
    name="airbnb_search_agent",
    seed="airbnb_search_agent_seed_phrase",
    port=8001,
    mailbox=True,  # Required for ASI discoverability
    publish_agent_details=True  # Required for ASI discoverability
)

# Print the agent's address for reference
print(f"Your agent's address is: {agent.address}")

# Set up rate limiting protocol
proto = QuotaProtocol(
    storage_reference=agent.storage,
    name="AirbnbSearchProtocol",
    version="0.1.0",
    default_rate_limit=RateLimit(window_size_minutes=60, max_requests=100),
)

# Health check implementation
class HealthCheck(Model):
    pass

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

class AgentHealth(Model):
    agent_name: str
    status: HealthStatus

def agent_is_healthy() -> bool:
    """Check if the agent's MCP client is working"""
    try:
        return chat_proto.mcp_manager is not None
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

# Health monitoring protocol
health_protocol = QuotaProtocol(
    storage_reference=agent.storage, 
    name="HealthProtocol", 
    version="0.1.0"
)

@health_protocol.on_message(HealthCheck, replies={AgentHealth})
async def handle_health_check(ctx: Context, sender: str, msg: HealthCheck):
    """Handle health check requests"""
    status = HealthStatus.UNHEALTHY
    try:
        if agent_is_healthy():
            status = HealthStatus.HEALTHY
    except Exception as err:
        ctx.logger.error(f"Health check error: {err}")
    finally:
        await ctx.send(
            sender, 
            AgentHealth(
                agent_name="airbnb_search_agent", 
                status=status
            )
        )

# Connect to the Airbnb MCP server
async def connect_to_airbnb_mcp():
    """Connect to the Airbnb MCP server"""
    airbnb_server = MCPServerInfo(
        server_id="airbnb",
        server_path="",  # Not using a file path
        description="Airbnb search and listing details",
        is_npx=True,
        npx_package="@openbnb/mcp-server-airbnb",
        extra_args=["--ignore-robots-txt"]  # Optional: ignoring robots.txt
    )
    
    success = await mcp_manager.connect_server(airbnb_server)
    if success:
        print("Successfully connected to Airbnb MCP server")
    else:
        print("Failed to connect to Airbnb MCP server")

# Include all protocols
agent.include(health_protocol, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)
agent.include(mcp_management_proto, publish_manifest=True)


# Set up cleanup handler
async def cleanup():
    """Clean up resources when shutting down"""
    if mcp_manager:
        await mcp_manager.cleanup()

if __name__ == "__main__":
    try:
        # Connect to Airbnb MCP server
        asyncio.create_task(connect_to_airbnb_mcp())
        
        # Run the agent
        agent.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        asyncio.run(cleanup())
    finally:
        # Ensure cleanup is called
        asyncio.run(cleanup())