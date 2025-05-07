# agent.py
import os
from enum import Enum
import asyncio

from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from uagents_core.models import ErrorMessage

from chat_proto import chat_proto, struct_output_client_proto, FoodRequest
from mcp_client import connect_to_food_mcp, cleanup_mcp_connection

# Create the agent
agent = Agent(
    name="food_nutrition_assistant",
    port=8003,
    mailbox=True
)

# Print the agent's address for reference
print(f"Your agent's address is: {agent.address}")

# Set up rate limiting protocol
proto = QuotaProtocol(
    storage_reference=agent.storage,
    name="Food-Protocol",
    version="0.1.0",
    default_rate_limit=RateLimit(window_size_minutes=60, max_requests=30),
)

class FoodResponse(Model):
    """Response with food information"""
    results: str

# Handle direct food requests
@proto.on_message(
    FoodRequest, replies={FoodResponse, ErrorMessage}
)
async def handle_request(ctx: Context, sender: str, msg: FoodRequest):
    ctx.logger.info(f"Received food request of type: {msg.request_type}")
    try:
        if msg.request_type == "search":
            query = msg.parameters.get("query")
            if not query:
                raise ValueError("Missing query parameter")
            
            from mcp_client import search_food_products
            results = await search_food_products(query)
            
        elif msg.request_type == "nutrition":
            product_name = msg.parameters.get("product_name")
            if not product_name:
                raise ValueError("Missing product_name parameter")
            
            from mcp_client import get_nutrition_facts
            results = await get_nutrition_facts(product_name)
            
        elif msg.request_type == "ingredients":
            product_name = msg.parameters.get("product_name")
            if not product_name:
                raise ValueError("Missing product_name parameter")
            
            from mcp_client import analyze_ingredients
            results = await analyze_ingredients(product_name)
            
        else:
            results = f"Unknown request type: {msg.request_type}"
            
        ctx.logger.info(f"Successfully processed food request")
        await ctx.send(sender, FoodResponse(results=results))
    except Exception as err:
        ctx.logger.error(f"Error in handle_request: {err}")
        await ctx.send(sender, ErrorMessage(error=str(err)))

# Include the main protocol
agent.include(proto, publish_manifest=True)

# Health check implementation
def agent_is_healthy() -> bool:
    """
    Check if the agent's food capabilities are working
    """
    try:
        import asyncio
        from mcp_client import mcp_session
        
        # Check if connected to Food MCP server
        return mcp_session is not None
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

class HealthCheck(Model):
    pass

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

class AgentHealth(Model):
    agent_name: str
    status: HealthStatus

# Health monitoring protocol
health_protocol = QuotaProtocol(
    storage_reference=agent.storage, name="HealthProtocol", version="0.1.0"
)

@health_protocol.on_message(HealthCheck, replies={AgentHealth})
async def handle_health_check(ctx: Context, sender: str, msg: HealthCheck):
    status = HealthStatus.UNHEALTHY
    try:
        if agent_is_healthy():
            status = HealthStatus.HEALTHY
    except Exception as err:
        ctx.logger.error(f"Health check error: {err}")
    finally:
        await ctx.send(
            sender, 
            AgentHealth(agent_name="food_nutrition_assistant", status=status)
        )

# Include all protocols
agent.include(health_protocol, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)
agent.include(struct_output_client_proto, publish_manifest=True)

# Initialize MCP connection on startup
@agent.on_event("startup")
async def on_startup(ctx: Context):
    """Connect to MCP server on startup"""
    ctx.logger.info("Connecting to Food MCP server on startup")
    success = await connect_to_food_mcp()
    if success:
        ctx.logger.info("Successfully connected to Food MCP server")
    else:
        ctx.logger.error("Failed to connect to Food MCP server")

if __name__ == "__main__":
    try:
        # Run the agent - connection will happen in the startup event
        agent.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        asyncio.run(cleanup_mcp_connection())