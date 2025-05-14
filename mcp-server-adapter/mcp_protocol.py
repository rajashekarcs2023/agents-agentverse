# mcp_protocol.py

from typing import Dict, Any
from uagents import Model
from uagents_core.protocol import ProtocolSpecification

class ListTools(Model):
    message: str

class ListToolsResponse(Model):
    tools: list[dict[str, Any]]

class CallTool(Model):
    tool: str
    args: Dict[str, Any]

class CallToolResponse(Model):
    message: str

# Only define initiating messages and their replies
mcp_protocol_spec = ProtocolSpecification(
    name="MCPProtocol",
    version="0.1.0",
    interactions={
        ListTools: {ListToolsResponse},
        CallTool: {CallToolResponse}
    },
    roles={
        "client": set(),
        "server": {ListTools, CallTool}
    }
)
