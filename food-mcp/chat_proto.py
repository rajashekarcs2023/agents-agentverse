# chat_proto.py
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict
from textwrap import dedent

from uagents import Context, Model, Protocol

# Import the necessary components of the chat protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from mcp_client import search_food_products, get_nutrition_facts, analyze_ingredients

# Replace the AI Agent Address with an LLM that supports StructuredOutput
# OpenAI Agent: agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y
# Claude.ai Agent: agent1qvk7q2av3e2y5gf5s90nfzkc8a48q3wdqeevwrtgqfdl0k78rspd6f2l4dx
AI_AGENT_ADDRESS = 'agent1qvk7q2av3e2y5gf5s90nfzkc8a48q3wdqeevwrtgqfdl0k78rspd6f2l4dx'

if not AI_AGENT_ADDRESS:
    raise ValueError("AI_AGENT_ADDRESS not set")

def create_text_chat(text: str, end_session: bool = True) -> ChatMessage:
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)
        
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )

chat_proto = Protocol(spec=chat_protocol_spec)
struct_output_client_proto = Protocol(
    name="StructuredOutputClientProtocol", version="0.1.0"
)

class FoodRequest(Model):
    """Model for requesting food information"""
    request_type: str  # "search", "nutrition", or "ingredients"
    parameters: Dict[str, Any]

class StructuredOutputPrompt(Model):
    prompt: str
    output_schema: dict[str, Any]

class StructuredOutputResponse(Model):
    output: dict[str, Any]

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Check if message has content before trying to access it
    if msg.content and any(isinstance(item, TextContent) for item in msg.content):
        # Get the first TextContent item
        text_content = next((item for item in msg.content if isinstance(item, TextContent)), None)
        if text_content:
            ctx.logger.info(f"Got a message from {sender}: {text_content.text}")
    else:
        ctx.logger.info(f"Got a message from {sender} without text content")
    
    ctx.storage.set(str(ctx.session), sender)
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Got a start session message from {sender}")
            continue
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Processing text message: {item.text}")
            ctx.storage.set(str(ctx.session), sender)
            
            prompt_text = dedent(f"""
                Extract the food information request from this message:

                "{item.text}"
                
                The user wants to get food information. Extract:
                1. The request_type: One of "search", "nutrition", or "ingredients"
                2. The parameters required for that request type:
                   
                   For search requests:
                   - query: The search query for food products
                   
                   For nutrition requests:
                   - product_name: The name of the food product
                   
                   For ingredients requests:
                   - product_name: The name of the food product
                
                Only include parameters that are mentioned or can be reasonably inferred.
                
                If the user asks about what's in a food, classify as "ingredients".
                If the user asks about calories, nutrients, protein, etc., classify as "nutrition".
                If the user is looking for types of foods or asking to find products, classify as "search".
            """)
            
            try:
                await ctx.send(
                    AI_AGENT_ADDRESS,
                    StructuredOutputPrompt(
                        prompt=prompt_text,
                        output_schema=FoodRequest.schema()
                    ),
                )
            except Exception as e:
                ctx.logger.error(f"Error sending to AI agent: {e}")
                # Fallback response
                fallback_msg = "I'm having trouble connecting to my AI processing component. Please try a simpler query or try again later."
                await ctx.send(
                    sender,
                    create_text_chat(fallback_msg)
                )
        else:
            ctx.logger.info(f"Got unexpected content type: {type(item)}")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )

@struct_output_client_proto.on_message(StructuredOutputResponse)
async def handle_structured_output_response(
    ctx: Context, sender: str, msg: StructuredOutputResponse
):
    try:
        session_sender = ctx.storage.get(str(ctx.session))
        if session_sender is None:
            ctx.logger.error(
                "Discarding message because no session sender found in storage"
            )
            return

        output_str = str(msg.output)
        if "<UNKNOWN>" in output_str:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "Sorry, I couldn't identify what food information you're looking for. Please specify if you want to search for food products, get nutrition facts, or analyze ingredients."
                ),
            )
            return

        # Parse the output - with additional error handling
        try:
            request = FoodRequest.parse_obj(msg.output)
        except Exception as parse_err:
            ctx.logger.error(f"Error parsing output: {parse_err}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I had trouble understanding the request. Please try rephrasing your question."
                ),
            )
            return
        
        # Extra validation
        if not request.request_type or not request.parameters:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I couldn't identify the request type or parameters. Please provide more details for your food query."
                ),
            )
            return

        result = ""
        try:
            if request.request_type == "search":
                # Get search parameters
                query = request.parameters.get("query")
                
                if not query:
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a search term to find food products. Please specify what food you're looking for."
                        ),
                    )
                    return
                    
                result = await search_food_products(query)
            elif request.request_type == "nutrition":
                # Get nutrition parameters
                product_name = request.parameters.get("product_name")
                
                if not product_name:
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a product name to provide nutrition facts. Please specify which food product you're interested in."
                        ),
                    )
                    return
                    
                result = await get_nutrition_facts(product_name)
            elif request.request_type == "ingredients":
                # Get ingredients parameters
                product_name = request.parameters.get("product_name")
                
                if not product_name:
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a product name to analyze ingredients. Please specify which food product you're interested in."
                        ),
                    )
                    return
                    
                result = await analyze_ingredients(product_name)
            else:
                await ctx.send(
                    session_sender,
                    create_text_chat(
                        f"I don't recognize the request type '{request.request_type}'. Please ask for a 'search', 'nutrition', or 'ingredients'."
                    ),
                )
                return
                
            # Make sure result is a string
            if not isinstance(result, str):
                result = str(result)
                
            chat_message = create_text_chat(result)
            await ctx.send(session_sender, chat_message)
        except Exception as tool_err:
            ctx.logger.error(f"Error calling MCP tool: {tool_err}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    f"I encountered an error while getting the food information: {str(tool_err)}"
                )
            )
    except Exception as outer_err:
        ctx.logger.error(f"Outer exception in handle_structured_output_response: {outer_err}")
        try:
            session_sender = ctx.storage.get(str(ctx.session))
            if session_sender:
                await ctx.send(
                    session_sender,
                    create_text_chat(
                        "Sorry, I encountered an unexpected error while processing your request. Please try again later."
                    )
                )
        except Exception as final_err:
            ctx.logger.error(f"Final error recovery failed: {final_err}")