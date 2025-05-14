# src/mcp_protocol.py
from typing import Dict, List, Any, Optional
from uagents import Model, Protocol

class MCPListToolsRequest(Model):
    """Request to list available tools"""
    pass

class MCPTool(Model):
    """Representation of an MCP tool"""
    name: str
    description: str
    inputSchema: Dict[str, Any]

class MCPListToolsResponse(Model):
    """Response with available tools"""
    tools: List[MCPTool]

class MCPCallToolRequest(Model):
    """Request to call a specific tool"""
    tool: str
    args: Dict[str, Any]

class MCPCallToolResponse(Model):
    """Response from tool execution"""
    content: str
    error: Optional[str] = None

# Create protocol
# Note: We're just defining the protocol here.
# The message registration is handled by the agent.on_message decorators.
mcp_protocol = Protocol(
    name="MCPServerProtocol",
    version="0.1.0"
)