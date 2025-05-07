# chat_proto.py
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict
from textwrap import dedent
import logging
import time
import asyncio

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

from mcp_client import search_airbnb_listings, get_airbnb_listing_details

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

# Timeout check function for AI agent response
async def check_ai_response_timeout(ctx: Context, session_sender: str, timeout_seconds: int = 15):
    """Check if we've received a response from the AI agent within the timeout period"""
    # Wait for the timeout period
    await asyncio.sleep(timeout_seconds)
    
    # Check if we're still waiting for a response
    waiting_flag = ctx.storage.get("waiting_for_ai_response")
    request_time = ctx.storage.get("ai_request_time")
    
    if waiting_flag == "true":
        elapsed = "unknown"
        if request_time:
            try:
                elapsed = round(time.time() - float(request_time), 2)
            except ValueError:
                pass
        
        ctx.logger.warning(f"No response received from AI agent after {elapsed} seconds")
        ctx.logger.warning(f"This may indicate a communication issue with the AI agent: {AI_AGENT_ADDRESS}")
        
        # Send a message to the user
        try:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I'm having trouble getting a response from my AI assistant. Let me try a direct search instead."
                )
            )
            
            # Attempt a direct search with the default parameters
            ctx.logger.info("Attempting direct search as fallback")
            location = "San Francisco"
            limit = 2
            
            # Call search function directly
            result_dict = await search_airbnb_listings(location, limit=limit)
            
            if result_dict.get("success", False):
                formatted_output = result_dict.get("formatted_output", "No results available")
                await ctx.send(session_sender, create_text_chat(formatted_output))
            else:
                await ctx.send(
                    session_sender,
                    create_text_chat(
                        f"I'm sorry, I couldn't search for Airbnb listings at this time. Please try again later."
                    )
                )
        except Exception as e:
            ctx.logger.error(f"Error in timeout handler: {e}")

# Add a debug message handler to catch all messages
# Note: Protocol doesn't have on_event, we need to use a specific message type
# We'll use Model as a base class to catch messages
class AnyMessage(Model):
    pass

@chat_proto.on_message(AnyMessage)
async def handle_any_message(ctx: Context, sender: str, msg: AnyMessage):
    ctx.logger.info(f"DEBUG HANDLER: Received message from {sender}")
    ctx.logger.info(f"Message type: {type(msg)}")
    ctx.logger.info(f"Is from AI agent: {sender == AI_AGENT_ADDRESS}")
    
    # Try to extract more information about the message
    try:
        if hasattr(msg, '__dict__'):
            ctx.logger.info(f"Message attributes: {msg.__dict__}")
        else:
            ctx.logger.info(f"Message string representation: {str(msg)}")
    except Exception as e:
        ctx.logger.info(f"Error inspecting message: {e}")

class AirbnbRequest(Model):
    """Model for requesting Airbnb information"""
    request_type: str  # "search" or "details"
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
                Extract the Airbnb request information from this message:

                "{item.text}"
                
                The user wants to get Airbnb information. Extract:
                1. The request_type: One of "search" or "details"
                2. The parameters required for that request type:
                   
                   For search requests:
                   - location: The location to search for listings
                   - checkin: Check-in date (YYYY-MM-DD) if specified
                   - checkout: Check-out date (YYYY-MM-DD) if specified
                   - adults: Number of adults if specified (default: 2)
                   - children: Number of children if specified
                   - infants: Number of infants if specified
                   - pets: Number of pets if specified
                   - minPrice: Minimum price if specified
                   - maxPrice: Maximum price if specified
                   
                   For details requests:
                   - id: The ID of the Airbnb listing
                   - checkin: Check-in date (YYYY-MM-DD) if specified
                   - checkout: Check-out date (YYYY-MM-DD) if specified
                
                Only include parameters that are mentioned or can be reasonably inferred.
                
                If the user asks for details about a specific listing, classify as "details".
                If the user is looking for listings in a location, classify as "search".
            """)
            
            ctx.logger.info(f"Preparing to send prompt to AI agent: {AI_AGENT_ADDRESS}")
            ctx.logger.info(f"Prompt text: {prompt_text[:100]}...")
            
            try:
                ctx.logger.info("Sending prompt to AI agent...")
                try:
                    # Set a flag in storage to track that we're waiting for AI response
                    ctx.storage.set("waiting_for_ai_response", "true")
                    ctx.storage.set("ai_request_time", str(time.time()))
                    ctx.logger.info(f"Set waiting flag in storage: {ctx.storage.get('waiting_for_ai_response')}")
                    
                    # Send the prompt to the AI agent
                    await ctx.send(
                        AI_AGENT_ADDRESS,
                        StructuredOutputPrompt(
                            prompt=prompt_text,
                            output_schema=AirbnbRequest.schema()
                        ),
                    )
                    ctx.logger.info("Successfully sent prompt to AI agent")
                    ctx.logger.info(f"Now waiting for response from: {AI_AGENT_ADDRESS}")
                    
                    # Schedule a timeout check
                    ctx.logger.info("Scheduling timeout check for AI response")
                    asyncio.create_task(check_ai_response_timeout(ctx, session_sender))
                except Exception as send_err:
                    ctx.logger.error(f"Error sending prompt: {send_err}")
                    import traceback
                    ctx.logger.error(f"Traceback: {traceback.format_exc()}")
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
        ctx.logger.info(f"Received structured output response from {sender}")
        ctx.logger.info(f"Output type: {type(msg.output)}")
        ctx.logger.info(f"Output content: {msg.output}")
        ctx.logger.info(f"Is AI agent response: {sender == AI_AGENT_ADDRESS}")
        
        session_sender = ctx.storage.get(str(ctx.session))
        if session_sender is None:
            ctx.logger.error(
                "Discarding message because no session sender found in storage"
            )
            return

        output_str = str(msg.output)
        if "<UNKNOWN>" in output_str:
            ctx.logger.info("Output contains <UNKNOWN>, sending clarification request")
            await ctx.send(
                session_sender,
                create_text_chat(
                    "Sorry, I couldn't understand what Airbnb information you're looking for. Please specify if you want to search for listings in a location or get details about a specific listing."
                ),
            )
            return

        # Check if we were waiting for this response
        waiting_flag = ctx.storage.get("waiting_for_ai_response")
        ctx.logger.info(f"Waiting flag status: {waiting_flag}")
        
        # Clear the waiting flag
        if waiting_flag == "true":
            ctx.storage.set("waiting_for_ai_response", "false")
            ctx.logger.info("Cleared waiting flag")
        
        # Parse the output - with additional error handling
        try:
            ctx.logger.info("Parsing output to AirbnbRequest model")
            ctx.logger.info(f"Raw output before parsing: {msg.output}")
            request = AirbnbRequest.parse_obj(msg.output)
            ctx.logger.info(f"Successfully parsed request: {request.request_type} with parameters: {request.parameters}")
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
            ctx.logger.info("Missing request_type or parameters, sending clarification request")
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I couldn't identify the request type or parameters. Please provide more details for your Airbnb query."
                ),
            )
            return

        try:
            if request.request_type == "search":
                ctx.logger.info("Processing search request")
                # Get search parameters
                location = request.parameters.get("location")
                
                if not location:
                    ctx.logger.info("No location provided, asking for clarification")
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a location to search for Airbnb listings. Please specify where you want to stay."
                        ),
                    )
                    return
                
                # Get optional parameters
                checkin = request.parameters.get("checkin")
                checkout = request.parameters.get("checkout")
                adults = request.parameters.get("adults", 2)
                children = request.parameters.get("children")
                infants = request.parameters.get("infants")
                pets = request.parameters.get("pets")
                min_price = request.parameters.get("minPrice")
                max_price = request.parameters.get("maxPrice")
                
                # Build kwargs
                kwargs = {}
                if checkin: kwargs["checkin"] = checkin
                if checkout: kwargs["checkout"] = checkout
                if adults: kwargs["adults"] = adults
                if children: kwargs["children"] = children
                if infants: kwargs["infants"] = infants
                if pets: kwargs["pets"] = pets
                if min_price: kwargs["minPrice"] = min_price
                if max_price: kwargs["maxPrice"] = max_price
                
                # Determine limit based on request (if number is mentioned)
                limit = 4  # Default
                for key, value in request.parameters.items():
                    if key == "limit" and isinstance(value, int):
                        limit = value
                
                # Extract number from text if it contains specific numbers
                query_text = item.text.lower() if 'item' in locals() and hasattr(item, 'text') else ""
                if "2 airbnb" in query_text or "two airbnb" in query_text or "2 rentals" in query_text or "two rentals" in query_text:
                    limit = 2
                elif "3 airbnb" in query_text or "three airbnb" in query_text or "3 rentals" in query_text or "three rentals" in query_text:
                    limit = 3
                
                ctx.logger.info(f"Calling search_airbnb_listings with location: {location}, limit: {limit}, kwargs: {kwargs}")
                
                # Call the search function with detailed logging
                ctx.logger.info(f"About to call search_airbnb_listings with location={location}, limit={limit}, kwargs={kwargs}")
                try:
                    result_dict = await search_airbnb_listings(location, limit=limit, **kwargs)
                    ctx.logger.info(f"Search function returned: {type(result_dict)}")
                    ctx.logger.info(f"Search result success: {result_dict.get('success', False)}")
                    ctx.logger.info(f"Search result keys: {result_dict.keys() if isinstance(result_dict, dict) else 'Not a dict'}")
                except Exception as search_err:
                    ctx.logger.error(f"Exception during search: {search_err}")
                    import traceback
                    ctx.logger.error(f"Search error traceback: {traceback.format_exc()}")
                    result_dict = {"success": False, "message": f"Error during search: {str(search_err)}"}
                
                # Check if successful and get formatted output
                if result_dict.get("success", False):
                    formatted_output = result_dict.get("formatted_output", "No results available")
                    listings = result_dict.get("listings", [])
                    total_listings = result_dict.get("total_listings", 0)
                    
                    # Add a summary line
                    summary = f"Found {total_listings} listings in {location}. Showing the top {len(listings)}.\n"
                    result = summary + formatted_output
                    
                    ctx.logger.info(f"Sending successful search result (length: {len(result)})")
                else:
                    result = f"Sorry, I couldn't find Airbnb listings in {location}: {result_dict.get('message', 'Unknown error')}"
                    ctx.logger.info(f"Sending search error message: {result}")
            
            elif request.request_type == "details":
                ctx.logger.info("Processing details request")
                # Get listing ID
                listing_id = request.parameters.get("id")
                
                if not listing_id:
                    ctx.logger.info("No listing ID provided, asking for clarification")
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a listing ID to get detailed information. Please specify which Airbnb listing you're interested in."
                        ),
                    )
                    return
                
                # Get optional parameters
                checkin = request.parameters.get("checkin")
                checkout = request.parameters.get("checkout")
                
                # Build kwargs
                kwargs = {}
                if checkin: kwargs["checkin"] = checkin
                if checkout: kwargs["checkout"] = checkout
                
                ctx.logger.info(f"Calling get_airbnb_listing_details with id: {listing_id}, kwargs: {kwargs}")
                
                # Call the details function
                result_dict = await get_airbnb_listing_details(listing_id, **kwargs)
                
                ctx.logger.info(f"Details result success: {result_dict.get('success', False)}")
                
                # Check if successful and get formatted output
                if result_dict.get("success", False):
                    formatted_output = result_dict.get("formatted_output", "No details available")
                    details = result_dict.get("details", {})
                    
                    # Add a title line
                    title = f"Details for Airbnb listing: {details.get('name', listing_id)}\n"
                    result = title + formatted_output
                    
                    ctx.logger.info(f"Sending successful details result (length: {len(result)})")
                else:
                    result = f"Sorry, I couldn't get details for listing {listing_id}: {result_dict.get('message', 'Unknown error')}"
                    ctx.logger.info(f"Sending details error message: {result}")
            
            else:
                ctx.logger.info(f"Unknown request type: {request.request_type}")
                result = f"I don't recognize the request type '{request.request_type}'. Please ask for a 'search' or 'details'."
            
            # Send the result back to the user
            ctx.logger.info("Creating text chat message to send back to user")
            chat_message = create_text_chat(result)
            ctx.logger.info(f"Sending response to {session_sender}")
            await ctx.send(session_sender, chat_message)
            ctx.logger.info("Response sent successfully")
                
        except Exception as tool_err:
            ctx.logger.error(f"Error calling MCP tool: {tool_err}")
            import traceback
            ctx.logger.error(f"Error traceback: {traceback.format_exc()}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    f"I encountered an error while getting the Airbnb information: {str(tool_err)}"
                )
            )
    except Exception as outer_err:
        ctx.logger.error(f"Outer exception in handle_structured_output_response: {outer_err}")
        import traceback
        ctx.logger.error(f"Error traceback: {traceback.format_exc()}")
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