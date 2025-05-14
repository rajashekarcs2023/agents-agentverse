# test_protocol.py
from uagents import Agent, Context, Model, Protocol

# Define a simple model
class HelloMessage(Model):
    message: str

# Create an agent
agent = Agent(name="test_agent", mailbox=True)

# Check if include method exists
if hasattr(agent, 'include'):
    print("The 'include' method exists on the Agent class")
    
    # Create a protocol
    protocol = Protocol(name="TestProtocol", version="0.1.0")
    
    # Try to include the protocol
    try:
        agent.include(protocol)
        print("Successfully included the protocol")
    except Exception as e:
        print(f"Error including protocol: {e}")
else:
    print("The 'include' method does not exist on the Agent class")
    print("Available methods:", [method for method in dir(agent) if not method.startswith('_')])

# Define a message handler
@agent.on_message(HelloMessage)
async def handle_hello(ctx: Context, sender: str, msg: HelloMessage):
    print(f"Received: {msg.message}")

if __name__ == "__main__":
    print(f"Agent address: {agent.address}")
    print(f"uAgents version: {getattr(Agent, '__version__', 'unknown')}")
    agent.run()