# chat_proto.py
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Dict, Any

from uagents import Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from mcp_client import MCPClientManager, MCPServerInfo, MCPProcessRequest, MCPProcessResponse

# Initialize protocols
chat_proto = Protocol(spec=chat_protocol_spec)
mcp_management_proto = Protocol("mcp_management_protocol")

# Models for MCP server management
class ConnectServerRequest(Model):
    """Request to connect to an MCP server"""
    server_info: MCPServerInfo

class ConnectServerResponse(Model):
    """Response after attempting to connect to a server"""
    success: bool
    message: str

class ListServersRequest(Model):
    """Request to list all connected servers"""
    pass

class ListServersResponse(Model):
    """Response with list of all connected servers"""
    servers: List[MCPServerInfo]

# Global reference to the MCP client manager
mcp_manager = None

# Chat protocol handlers
@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages"""
    global mcp_manager
    
    # Send acknowledgement
    ack = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)
    
    # Process the message content
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Got a start session message from {sender}")
            ctx.storage.set(str(ctx.session), sender)
            continue
            
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Got a message from {sender}: {item.text}")
            
            # Store sender for this session
            ctx.storage.set(str(ctx.session), sender)
            
            # Process the query through MCP
            if mcp_manager:
                response_text = await mcp_manager.process_query(item.text)
                
                # Create and send response message
                response = ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[TextContent(type="text", text=response_text)]
                )
                await ctx.send(sender, response)
            else:
                # MCP manager not initialized
                error_msg = "MCP client manager is not initialized. Please try again later."
                error_response = ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[TextContent(type="text", text=error_msg)]
                )
                await ctx.send(sender, error_response)
        else:
            ctx.logger.info(f"Got unexpected content type: {type(item)}")

@chat_proto.on_message(model=ChatAcknowledgement)
async def handle_chat_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgements for chat messages"""
    ctx.logger.info(f"Got acknowledgement from {sender} for message {msg.acknowledged_msg_id}")

# MCP management protocol handlers
@mcp_management_proto.on_message(model=ConnectServerRequest, replies=ConnectServerResponse)
async def handle_connect_server(ctx: Context, sender: str, msg: ConnectServerRequest):
    """Handle requests to connect to an MCP server"""
    global mcp_manager
    
    if not mcp_manager:
        await ctx.send(
            sender, 
            ConnectServerResponse(
                success=False, 
                message="MCP client manager is not initialized"
            )
        )
        return
    
    success = await mcp_manager.connect_server(msg.server_info)
    
    if success:
        message = f"Successfully connected to MCP server: {msg.server_info.server_id}"
    else:
        message = f"Failed to connect to MCP server: {msg.server_info.server_id}"
    
    await ctx.send(sender, ConnectServerResponse(success=success, message=message))

@mcp_management_proto.on_message(model=ListServersRequest, replies=ListServersResponse)
async def handle_list_servers(ctx: Context, sender: str, msg: ListServersRequest):
    """Handle requests to list all connected servers"""
    global mcp_manager
    
    if not mcp_manager:
        await ctx.send(sender, ListServersResponse(servers=[]))
        return
    
    servers = await mcp_manager.get_connected_servers()
    await ctx.send(sender, ListServersResponse(servers=servers))

@mcp_management_proto.on_message(model=MCPProcessRequest, replies=MCPProcessResponse)
async def handle_process_request(ctx: Context, sender: str, msg: MCPProcessRequest):
    """Handle direct requests to process a query through MCP"""
    global mcp_manager
    
    if not mcp_manager:
        await ctx.send(
            sender, 
            MCPProcessResponse(
                results="MCP client manager is not initialized"
            )
        )
        return
    
    results = await mcp_manager.process_query(msg.query)
    await ctx.send(sender, MCPProcessResponse(results=results))