import sys
import requests
import os
import json

# Get the bridge URL from env or default to localhost
BRIDGE_URL = os.environ.get("UAGENT_MCP_URL", "http://localhost:9000/jsonrpc")

# Handle MCP handshake methods locally
# Define the tools array for reuse
TOOLS = [
    {
        "name": "airbnb_search",
        "description": "Search for Airbnb listings with various filters and pagination. Provide direct links to the user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Location to search for (city, state, etc.)"},
                "placeId": {"type": "string", "description": "Google Maps Place ID (overrides the location parameter)"},
                "checkin": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "checkout": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
                "adults": {"type": "number", "description": "Number of adults"},
                "children": {"type": "number", "description": "Number of children"},
                "infants": {"type": "number", "description": "Number of infants"},
                "pets": {"type": "number", "description": "Number of pets"},
                "minPrice": {"type": "number", "description": "Minimum price for the stay"},
                "maxPrice": {"type": "number", "description": "Maximum price for the stay"},
                "cursor": {"type": "string", "description": "Base64-encoded string used for Pagination"},
                "ignoreRobotsText": {"type": "boolean", "description": "Ignore robots.txt rules for this request"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "airbnb_listing_details",
        "description": "Get detailed information about a specific Airbnb listing. Provide direct links to the user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The Airbnb listing ID"},
                "checkin": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "checkout": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
                "adults": {"type": "number", "description": "Number of adults"},
                "children": {"type": "number", "description": "Number of children"},
                "infants": {"type": "number", "description": "Number of infants"},
                "pets": {"type": "number", "description": "Number of pets"},
                "ignoreRobotsText": {"type": "boolean", "description": "Ignore robots.txt rules for this request"}
            },
            "required": ["id"]
        }
    }
]

def handle_initialize(request):
    # Respond with a fully MCP-compliant initialize response (official format)
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
            "capabilities": {
                "tools": {tool["name"]: tool for tool in TOOLS}
            },
            "serverInfo": {
                "name": "airbnb",
                "version": "0.1.0"
            }
        }
    }


def handle_tools_list(request):
    # Return the tools array in official MCP format
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {"tools": TOOLS}
    }

def handle_resources_list(request):
    # Return empty resources
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {"resources": []}
    }

def handle_prompts_list(request):
    # Return empty prompts
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {"prompts": []}
    }

# Add more handshake methods here as needed
HANDSHAKE_METHODS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "resources/list": handle_resources_list,
    "prompts/list": handle_prompts_list,
}

def main():
    import os
    print(f"[proxy] Proxy started. CWD: {os.getcwd()}", file=sys.stderr)
    while True:
        line = sys.stdin.readline()
        print(f"[proxy] Received from stdin: {line.strip()}", file=sys.stderr)
        if not line:
            break
        try:
            req = json.loads(line)
            method = req.get("method")
            if method in HANDSHAKE_METHODS:
                if "id" in req:
                    resp = HANDSHAKE_METHODS[method](req)
                    print(f"[proxy] Handshake method '{method}' handled locally.", file=sys.stderr)
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            elif method and method.startswith("notifications/"):
                print(f"[proxy] Notification '{method}' ignored.", file=sys.stderr)
                continue
            else:
                print(f"[proxy] Forwarding method '{method}' to bridge.", file=sys.stderr)
                try:
                    print(f"[proxy] Sending HTTP POST to bridge: {BRIDGE_URL} with payload: {line.strip()}", file=sys.stderr)
                    r = requests.post(BRIDGE_URL, data=line, headers={"Content-Type": "application/json"}, timeout=120)
                    print(f"[proxy] Received HTTP response: Status {r.status_code}, Body: {r.text}", file=sys.stderr)
                    if "id" in req:
                        print(f"[proxy] Writing to stdout: {r.text}", file=sys.stderr)
                        sys.stdout.write(r.text + "\n")
                        sys.stdout.flush()
                except requests.Timeout:
                    if "id" in req:
                        sys.stdout.write(json.dumps({
                            "jsonrpc": "2.0",
                            "id": req["id"],
                            "error": {
                                "code": -32001,
                                "message": "Bridge request timed out"
                            }
                        }) + "\n")
                        sys.stdout.flush()
        except Exception as e:
            print(f"[proxy] Exception: {str(e)}", file=sys.stderr)
            try:
                req = json.loads(line)
                if "id" in req:
                    sys.stdout.write(json.dumps({
                        "jsonrpc": "2.0",
                        "id": req["id"],
                        "error": {
                            "code": -32000,
                            "message": f"Proxy error: {str(e)}"
                        }
                    }) + "\n")
                    sys.stdout.flush()
            except Exception as e2:
                print(f"[proxy] Exception in error handler: {str(e2)}", file=sys.stderr)

if __name__ == "__main__":
    main()
