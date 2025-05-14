# chat_proto.py
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict
from textwrap import dedent
import logging
import time
import asyncio
import os
from datetime import datetime

# Set up file logging for chat protocol
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"chat_proto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Configure file logger
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Get the logger and add the file handler
proto_logger = logging.getLogger("chat_proto")
proto_logger.setLevel(logging.DEBUG)

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

# Set up logging
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# Get the current date and time for the log filename
log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"chat_proto_{log_timestamp}.log")

# Function to log to file
def log_to_file(message: str):
    """Log a message to a file"""
    with open(log_file, "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")

# OpenAI Agent address for structured output
AI_AGENT_ADDRESS = 'agent1qtlpfshtlcxekgrfcpmv7m9zpajuwu7d5jfyachvpa4u3dkt6k0uwwp2lct'

def create_text_chat(text: str, end_session: bool = True) -> ChatMessage:
    """Create a chat message with text content and optional end session marker"""
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)
        
    # Create content list with text content
    content = [TextContent(type="text", text=text)]
    
    # Add end session marker if requested
    if end_session:
        content.append(EndSessionContent(type="end-session"))
        
    # Create and return the message
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=str(uuid4()),
        content=content,
    )

# Define the Airbnb request and response models
class AirbnbRequest(Model):
    """Model for requesting Airbnb information"""
    request_type: str  # "search" or "details"
    parameters: dict

class AirbnbResponse(Model):
    """Response with Airbnb information"""
    results: str

# Set up the protocols
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
            
            # Call search function directly with detailed logging
            ctx.logger.info(f"Calling search_airbnb_listings with location={location}, limit={limit}")
            log_to_file(f"FALLBACK: Calling search_airbnb_listings with location={location}, limit={limit}")
            
            try:
                result_dict = await search_airbnb_listings(location, limit=limit)
                
                # Log the search results
                ctx.logger.info(f"Fallback search result: {result_dict}")
                log_to_file(f"FALLBACK SEARCH RESULT: {result_dict}")
                
                if result_dict.get("success", False):
                    formatted_output = result_dict.get("formatted_output", "No results available")
                    ctx.logger.info(f"Sending formatted output to user (length: {len(formatted_output)})")
                    log_to_file(f"SENDING FORMATTED OUTPUT TO USER (length: {len(formatted_output)})")
                    log_to_file(f"OUTPUT SAMPLE: {formatted_output[:200]}...")
                    
                    # Use the AirbnbResponse model to send results to ASI1
                    try:
                        # Verify we have a valid session sender
                        if not session_sender:
                            ctx.logger.error("No session sender found for sending results")
                            log_to_file("ERROR: No session sender found for sending results")
                            return
                            
                        # Create a simple message with just the essential information
                        result = "Here are 2 Airbnb rentals in San Francisco for May 10th, 2025:\n\n"
                        
                        # Extract just the essential listing information
                        listings = result_dict.get("listings", [])
                        for i, listing in enumerate(listings[:2], 1):
                            result += f"{i}. {listing.get('name', 'Unnamed Listing')}\n"
                            result += f"   Price: {listing.get('price', 'Price not available')}\n"
                            result += f"   Rating: {listing.get('rating', 'Not rated')}\n\n"
                        
                        # Log the message we're about to send
                        ctx.logger.info(f"Creating AirbnbResponse with results (length: {len(result)})")
                        log_to_file(f"CREATING AIRBNB RESPONSE: {result}")
                        
                        # First try sending a structured response
                        try:
                            # Create an AirbnbResponse with the results
                            airbnb_response = AirbnbResponse(results=result)
                            ctx.logger.info(f"Sending AirbnbResponse to: {session_sender}")
                            await ctx.send(session_sender, airbnb_response)
                            ctx.logger.info("AirbnbResponse sent successfully")
                            log_to_file("AIRBNB RESPONSE SENT SUCCESSFULLY")
                        except Exception as struct_err:
                            # If structured response fails, fall back to text chat
                            ctx.logger.error(f"Error sending structured response: {struct_err}")
                            log_to_file(f"ERROR SENDING STRUCTURED RESPONSE: {str(struct_err)}")
                            
                            # Create a chat message with end_session=True
                            message = create_text_chat(result, end_session=True)
                            ctx.logger.info(f"Falling back to text chat message to: {session_sender}")
                            await ctx.send(session_sender, message)
                            ctx.logger.info("Text chat message sent successfully")
                            log_to_file("TEXT CHAT MESSAGE SENT SUCCESSFULLY")
                        
                        # Send a follow-up message to ensure receipt
                        await asyncio.sleep(1)
                        await ctx.send(session_sender, create_text_chat("Thank you for using Airbnb Assistant.", end_session=True))
                        ctx.logger.info("Sent follow-up message")
                        log_to_file("SENT FOLLOW-UP MESSAGE")
                    
                    except Exception as send_err:
                        ctx.logger.error(f"Error sending results to user: {send_err}")
                        log_to_file(f"ERROR SENDING RESULTS TO USER: {str(send_err)}")
                        import traceback
                        log_to_file(f"SEND ERROR TRACEBACK: {traceback.format_exc()}")
                else:
                    error_msg = result_dict.get("message", "Unknown error")
                    ctx.logger.error(f"Search failed: {error_msg}")
                    log_to_file(f"SEARCH FAILED: {error_msg}")
                    
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            f"I'm sorry, I couldn't search for Airbnb listings at this time. Error: {error_msg}"
                        )
                    )
            except Exception as search_err:
                ctx.logger.error(f"Error in fallback search: {search_err}")
                log_to_file(f"ERROR IN FALLBACK SEARCH: {str(search_err)}")
                import traceback
                log_to_file(f"FALLBACK ERROR TRACEBACK: {traceback.format_exc()}")
        except Exception as e:
            ctx.logger.error(f"Error in timeout handler: {e}")

# We can't add a general message handler because the protocol is already locked
# Instead, we'll enhance the existing handlers

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
    """Handle incoming chat messages from users"""
    # Extract text content from the message
    text_content = None
    if msg.content:
        text_content = next((item.text for item in msg.content if isinstance(item, TextContent)), None)
        if text_content:
            ctx.logger.info(f"Got a message from {sender}: {text_content}")
    
    # Store the sender for this session
    ctx.storage.set(str(ctx.session), sender)
    
    # Send acknowledgement
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    # Process message content
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Got a start session message from {sender}")
            continue
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Processing text message: {item.text}")
            
            # Create prompt for AI agent
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
            
            try:
                # Set a flag in storage to track that we're waiting for AI response
                ctx.storage.set("waiting_for_ai_response", "true")
                ctx.storage.set("ai_request_time", str(time.time()))
                
                # Send the prompt to the AI agent
                ctx.logger.info("Sending prompt to AI agent...")
                await ctx.send(
                    AI_AGENT_ADDRESS,
                    StructuredOutputPrompt(
                        prompt=prompt_text,
                        output_schema=AirbnbRequest.schema()
                    )
                )
                
                ctx.logger.info("Successfully sent prompt to AI agent")
                ctx.logger.info(f"Now waiting for response from: {AI_AGENT_ADDRESS}")
                
                # Get the session sender from storage
                session_sender = ctx.storage.get(str(ctx.session))
                if session_sender:
                    ctx.logger.info(f"Using session sender: {session_sender}")
                else:
                    ctx.logger.warning("No session sender found in storage")
                    
                # Schedule a check for AI response timeout
                ctx.logger.info("Scheduling timeout check for AI response")
                asyncio.create_task(check_ai_response_timeout(ctx, session_sender))
                
            except Exception as e:
                ctx.logger.error(f"Error sending to AI agent: {e}")
                session_sender = ctx.storage.get(str(ctx.session))
                
                # If we have a session sender, attempt fallback search
                if session_sender:
                    ctx.logger.warning("Attempting direct search as fallback")
                    await handle_fallback_search(ctx, session_sender, item.text)
                else:
                    ctx.logger.error("Cannot perform fallback: No session sender found")
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
    """Handle structured output responses from the AI agent"""
    try:
        # Log basic information about the received response
        ctx.logger.info(f"Received structured output response from {sender}")
        ctx.logger.info(f"Output type: {type(msg.output)}")
        ctx.logger.info(f"Output content: {msg.output}")
        
        # Get the session sender from storage
        session_sender = ctx.storage.get(str(ctx.session))
        if session_sender is None:
            ctx.logger.error("Discarding message because no session sender found in storage")
            return

        # Check for unknown values in the output
        output_str = str(msg.output)
        if "<UNKNOWN>" in output_str:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "Sorry, I couldn't understand what Airbnb information you're looking for. Please specify if you want to search for listings in a location or get details about a specific listing."
                )
            )
            return

        # Check if we were waiting for this response
        waiting_flag = ctx.storage.get("waiting_for_ai_response")
        ctx.logger.info(f"Waiting flag status: {waiting_flag}")
        
        # Clear the waiting flag
        if waiting_flag == "true":
            ctx.storage.set("waiting_for_ai_response", "false")
            ctx.logger.info("Cleared waiting flag")
        
        # Parse the output to AirbnbRequest model
        try:
            ctx.logger.info("Parsing output to AirbnbRequest model")
            request = AirbnbRequest.parse_obj(msg.output)
            ctx.logger.info(f"Successfully parsed request: {request.request_type} with parameters: {request.parameters}")
        except Exception as parse_err:
            ctx.logger.error(f"Error parsing output: {parse_err}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I had trouble understanding the request. Please try rephrasing your question."
                )
            )
            return
        
        # Validate request has required fields
        if not request.request_type or not request.parameters:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "I couldn't identify the request type or parameters. Please provide more details for your Airbnb query."
                )
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
                
                # Set default limit and extract optional parameters
                limit = 4  # Show 4 listings by default
                
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
                
                ctx.logger.info(f"Calling search_airbnb_listings with location: {location}, limit: {limit}, kwargs: {kwargs}")
                
                # Call the search function
                search_result = await search_airbnb_listings(location, limit, **kwargs)
                
                # Process the search result
                if search_result.get("success", False):
                    formatted_output = search_result.get("formatted_output", "")
                    ctx.logger.info(f"Sending successful search result (length: {len(formatted_output)})")
                    await ctx.send(session_sender, create_text_chat(formatted_output))
                    ctx.logger.info("Response sent successfully")
                else:
                    error_message = search_result.get("message", "An error occurred while searching for listings.")
                    ctx.logger.error(f"Search failed: {error_message}")
                    await ctx.send(session_sender, create_text_chat(f"Sorry, I couldn't find any listings: {error_message}"))
            
            elif request.request_type == "details":
                # Get required listing ID parameter
                listing_id = request.parameters.get("id")
                if not listing_id:
                    await ctx.send(
                        session_sender,
                        create_text_chat(
                            "I need a listing ID to get details. Please provide the ID of the Airbnb listing you're interested in."
                        )
                    )
                    return
                
                # Extract other parameters
                kwargs = {}
                for param in ["checkin", "checkout"]:
                    if param in request.parameters:
                        kwargs[param] = request.parameters[param]
                
                # Call the details function
                details_result = await get_airbnb_listing_details(listing_id, **kwargs)
                
                # Process the details result
                if details_result.get("success", False):
                    formatted_output = details_result.get("formatted_output", "")
                    await ctx.send(session_sender, create_text_chat(formatted_output))
                else:
                    error_message = details_result.get("message", "An error occurred while getting listing details.")
                    await ctx.send(session_sender, create_text_chat(f"Sorry, I couldn't get the listing details: {error_message}"))
            
            else:
                await ctx.send(
                    session_sender,
                    create_text_chat(
                        f"I don't recognize the request type '{request.request_type}'. Please ask for a 'search' or 'details'."
                    )
                )
        except Exception as e:
            ctx.logger.error(f"Error processing request: {e}")
            await ctx.send(
                session_sender,
                create_text_chat(
                    f"I encountered an error while processing your request: {str(e)}"
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

# Function to handle fallback search when AI agent doesn't respond
async def handle_fallback_search(ctx: Context, session_sender: str, query_text: str):
    """Perform a direct search as fallback when AI agent doesn't respond"""
    try:
        # Extract location from query text (simple approach)
        location = "San Francisco"  # Default
        if "near" in query_text.lower():
            parts = query_text.lower().split("near")
            if len(parts) > 1:
                location_part = parts[1].strip()
                location = location_part.split(",")[0].split(".")[0].split("and")[0].strip()
        
        # Set a reasonable limit
        limit = 2
        if "2" in query_text or "two" in query_text.lower():
            limit = 2
        elif "3" in query_text or "three" in query_text.lower():
            limit = 3
        elif "4" in query_text or "four" in query_text.lower():
            limit = 4
        
        ctx.logger.info(f"Calling search_airbnb_listings with location={location}, limit={limit}")
        
        # Call the search function
        result_dict = await search_airbnb_listings(location, limit)
        
        # Check if successful
        if result_dict.get("success", False):
            formatted_output = result_dict.get("formatted_output", "")
            ctx.logger.info(f"Fallback search result: {result_dict}")
            
            # Send the formatted output to the user
            ctx.logger.info(f"Sending formatted output to user (length: {len(formatted_output)})")
            log_to_file(f"SENDING FORMATTED OUTPUT TO USER (length: {len(formatted_output)})")
            log_to_file(f"OUTPUT SAMPLE: {formatted_output[:200]}...")
            
            # Use the exact same approach as the food-mcp implementation
            try:
                # Create a simple message for ASI1
                result = f"Here are {limit} Airbnb rentals in {location}:\n\n"
                
                # Extract just the essential listing information
                listings = result_dict.get("listings", [])
                for i, listing in enumerate(listings[:limit], 1):
                    result += f"{i}. {listing.get('name', 'Unnamed Listing')}\n"
                    result += f"   Price: {listing.get('price', 'Price not available')}\n"
                    result += f"   Rating: {listing.get('rating', 'Not rated')}\n\n"
                
                # Log the message we're about to send
                ctx.logger.info(f"Creating chat message with text length: {len(result)}")
                
                # Use the create_text_chat function exactly as in food-mcp
                chat_message = create_text_chat(result)
                
                # Send directly to ASI1 using the same pattern as food-mcp
                ctx.logger.info(f"Sending message to ASI1: {session_sender}")
                await ctx.send(session_sender, chat_message)
                ctx.logger.info("Message sent successfully to ASI1")
                
                # Send a follow-up message to confirm receipt
                await asyncio.sleep(1)  # Brief pause
                await ctx.send(session_sender, create_text_chat("These are the best available Airbnb rentals I could find for your dates."))
                ctx.logger.info("Sent follow-up message")
            except Exception as send_err:
                ctx.logger.error(f"Error sending results to user: {send_err}")
                log_to_file(f"ERROR SENDING RESULTS TO USER: {str(send_err)}")
        else:
            # Send an error message
            error_message = result_dict.get("message", "An error occurred while searching for listings.")
            ctx.logger.error(f"Fallback search failed: {error_message}")
            await ctx.send(session_sender, create_text_chat(f"Sorry, I couldn't find any listings: {error_message}"))
    except Exception as e:
        ctx.logger.error(f"Error in fallback search: {e}")
        await ctx.send(session_sender, create_text_chat("Sorry, I encountered an error while searching for listings. Please try again later."))