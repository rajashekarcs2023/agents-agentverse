import os
import sys
import json
import asyncio
import logging
import uuid
from aiohttp import web
from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol

# ========== CONFIGURATION =============
# Set this to the MCP server uAgent address on agentverse
UAGENT_SERVER_ADDRESS = os.environ.get("MCP_UAGENT_SERVER_ADDRESS", "agent1qvz20fv70zj4v0psjg5wxkufl36klj986yu2s5qrdhhl9g8c03p02q6hvwu")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", 9000))
CLIENT_AGENT_PORT = int(os.environ.get("CLIENT_AGENT_PORT", 9001))

# ========== LOGGING =============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_uagent_bridge")

# ========== UAGENT CLIENT SETUP =============
class MCPRequest(Model):
    tool_name: str
    parameters: dict
    request_id: str

class MCPResponse(Model):
    success: bool
    result: object = None
    error: str = None
    request_id: str = None

class UAgentBridgeClient:
    def __init__(self, target_address: str, port: int = 9001):
        self.target_address = target_address
        self.agent = Agent(name="bridge_client", port=port, mailbox=True)
        self.protocol = QuotaProtocol(
            storage_reference=self.agent.storage,
            name="Bridge-Protocol",
            version="0.1.0"
        )
        self.pending_futures = {}
        self._outgoing_queue = asyncio.Queue()
        self._setup_handlers()
        # Start the agent in a background thread
        import threading
        def start_agent(agent):
            agent.run()
        threading.Thread(target=start_agent, args=(self.agent,), daemon=True).start()
        # Start a background task to process the outgoing queue
        asyncio.get_event_loop().create_task(self._process_outgoing_queue())

    def _setup_handlers(self):
        @self.protocol.on_message(MCPResponse)
        async def handle_response(ctx: Context, sender: str, msg: MCPResponse):
            logger.info(f"Received response for request_id={msg.request_id}")
            fut = self.pending_futures.pop(msg.request_id, None)
            if fut:
                fut.set_result(msg)
            else:
                logger.warning(f"No pending future for request_id={msg.request_id}")
        @self.agent.on_interval(period=1.0)
        async def process_queue(ctx: Context):
            while not self._outgoing_queue.empty():
                target, req = await self._outgoing_queue.get()
                await ctx.send(target, req)
        self.agent.include(self.protocol, publish_manifest=True)

    async def _process_outgoing_queue(self):
        # Dummy coroutine to keep the event loop happy if not using on_interval
        while True:
            await asyncio.sleep(3600)

    async def call_tool(self, tool_name, parameters):
        req_id = str(uuid.uuid4())
        fut = asyncio.get_event_loop().create_future()
        self.pending_futures[req_id] = fut
        req = MCPRequest(tool_name=tool_name, parameters=parameters, request_id=req_id)
        await self._outgoing_queue.put((self.target_address, req))
        try:
            resp = await asyncio.wait_for(fut, timeout=90)
            return resp
        except Exception as e:
            self.pending_futures.pop(req_id, None)
            raise e

# ========== HTTP SERVER =============
bridge_client = UAgentBridgeClient(UAGENT_SERVER_ADDRESS, port=CLIENT_AGENT_PORT)

# Define a static TOOLS list for tools/list


async def handle_jsonrpc(request):
    try:
        data = await request.json()
        logger.info(f"Received JSON-RPC: {data}")
        jsonrpc_id = data.get("id")
        method = data.get("method")
        params = data.get("params", {})

        # Intercept tools/list and return static tools
        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "result": {"tools": TOOLS}
            }
            return web.json_response(response)

        # Forward all other methods to uAgent
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            resp = await bridge_client.call_tool(tool_name, tool_args)
            logger.info(f"[bridge] Called tool '{tool_name}' with arguments: {tool_args}")
        else:
            resp = await bridge_client.call_tool(method, params)
        logger.info(f"[bridge] Received from uAgent: {resp}")
        # --- Match official Airbnb MCP server response format exactly ---
        if resp.success:
            # Only keep the 'content' key and 'isError' if present
            result = resp.result
            # Remove any extra keys (like 'meta', 'annotations') for parity
            if isinstance(result, dict):
                filtered_result = {}
                if 'content' in result:
                    # Only keep 'type', 'text' in each content item
                    filtered_content = []
                    for item in result['content']:
                        filtered_item = {
                            'type': item.get('type', 'text'),
                            'text': item.get('text', '')
                        }
                        filtered_content.append(filtered_item)
                    filtered_result['content'] = filtered_content
                if 'isError' in result:
                    filtered_result['isError'] = result['isError']
                result = filtered_result
            error = None
        else:
            result = None
            error = resp.error or "Unknown error"
        response = {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "result": result
        }
        if error:
            response = {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "error": {"code": -32000, "message": error}
            }
        logger.info(f"[bridge] Sending HTTP response to proxy: {response}")
        return web.json_response(response, dumps=lambda x: json.dumps(x, ensure_ascii=False))
    except Exception as e:
        logger.exception("Error in handle_jsonrpc")
        return web.json_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}, status=500)


import aiohttp_cors

app = web.Application()

app.router.add_post("/jsonrpc", handle_jsonrpc)

# --- CORS support for browser UIs ---
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
    )
})
for route in list(app.router.routes()):
    cors.add(route)

if __name__ == "__main__":
    logger.info(f"Starting MCP-uAgent bridge on port {BRIDGE_PORT}")
    web.run_app(app, port=BRIDGE_PORT)
