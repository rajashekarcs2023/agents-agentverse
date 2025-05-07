# test_agent.py
import asyncio
from uuid import uuid4
from datetime import datetime

from uagents import Agent, Context, Model
from uagents.crypto import Identity

# Message models
class ChatMessage(Model):
    timestamp: datetime
    msg_id: str  # Using str instead of uuid4 function
    content: list

class TextContent(Model):
    type: str = "text"
    text: str

class EndSessionContent(Model):
    type: str = "end-session"

# Create a test agent
test_agent = Agent(
    name="test_agent",
    port=8005,
    endpoint=["http://localhost:8005/submit"],
)

# Store the Airbnb agent address
AIRBNB_AGENT_ADDRESS = "agent1q22atu36zvexz9sgg8unegmnn9ar3p4juzxcfqvf7wkgs3nwkjku6pxkry6"

# Create a simple chat message
def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=str(uuid4()),  # Convert UUID to string
        content=content,
    )

# Handle received messages
@test_agent.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Received message from {sender}")
    
    # Extract text content
    text_content = None
    for item in msg.content:
        if hasattr(item, 'type') and item.type == "text" and hasattr(item, 'text'):
            text_content = item.text
            break
    
    if text_content:
        ctx.logger.info(f"Message content: {text_content}")
    else:
        ctx.logger.info("No text content found in the message")
    
    # Check for end-session marker
    has_end_session = any(hasattr(item, 'type') and item.type == "end-session" for item in msg.content)
    if has_end_session:
        ctx.logger.info("Message has end-session marker")

# Send a request to the Airbnb agent
@test_agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Test agent started with address: {test_agent.address}")
    ctx.logger.info(f"Will send message to Airbnb agent: {AIRBNB_AGENT_ADDRESS}")
    
    # Wait a bit for the agent to fully start
    await asyncio.sleep(3)
    
    # Send a message to the Airbnb agent
    message = create_text_chat("Find two Airbnb rentals near San Francisco downtown for May 10th, 2025.")
    ctx.logger.info(f"Sending message to Airbnb agent: {message}")
    
    try:
        await ctx.send(AIRBNB_AGENT_ADDRESS, message)
        ctx.logger.info("Message sent successfully")
    except Exception as e:
        ctx.logger.error(f"Error sending message: {e}")

if __name__ == "__main__":
    test_agent.run()
