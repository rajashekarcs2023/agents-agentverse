from mcp.server.fastmcp import FastMCP
import random

# Create an MCP server named "weather"
mcp = FastMCP("weather")

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location
    
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # This is a mock implementation - in reality you'd call a weather API
    conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Stormy"]
    temps = list(range(60, 85))
    
    forecast = f"""
Weather Forecast for {latitude}, {longitude}:
Today: {random.choice(conditions)}, {random.choice(temps)}°F
Tomorrow: {random.choice(conditions)}, {random.choice(temps)}°F
Day After: {random.choice(conditions)}, {random.choice(temps)}°F
"""
    return forecast

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state
    
    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    # Mock implementation
    alerts = [
        "No active alerts for this state.",
        f"Severe Thunderstorm Warning for {state} until 5:00 PM.",
        f"Flash Flood Watch for {state} until midnight.",
        f"Heat Advisory for {state} until 8:00 PM."
    ]
    
    return random.choice(alerts)

if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport='stdio')