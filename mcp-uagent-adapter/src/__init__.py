"""
MCP uAgent Adapter Package

This package provides a clean adapter for integrating MCP servers with the uAgents framework.
"""

from .mcp_uagent_adapter import MCPUAgentAdapter, MCPTool, MCPToolParameter, MCPRequest, MCPResponse
from .mcp_uagent_client import MCPUAgentClient, MCPUAgentHTTPServer

__all__ = [
    'MCPUAgentAdapter',
    'MCPTool',
    'MCPToolParameter',
    'MCPRequest',
    'MCPResponse',
    'MCPUAgentClient',
    'MCPUAgentHTTPServer'
]
