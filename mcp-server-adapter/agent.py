from mcp_adapter import MCPAdapter
from uagents import Agent
from server import mcp
import os

adapter = MCPAdapter(mcp_server=mcp, openai_api_key="")
agent = Agent(name="weather_agent")

# Include protocols from the adapter
for proto in adapter.protocols:
    agent.include(proto, publish_manifest=True)

if __name__ == "__main__":
    adapter.run(agent)
