import traceback  # Import traceback for detailed error logging

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request  # Import jsonify
from langchain_core.messages import AIMessage, HumanMessage  # Import message types
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

# --- Configuration ---
load_dotenv()

AVAILABLE_MODELS = ["qwen2.5:7b", "qwen2.5:0.5b"]
STRINGS_URL = "http://localhost:8001/sse"
ARITHMETIC_URL = "http://localhost:8002/sse"
WEATHER_URL = "http://localhost:8003/sse"

# --- Flask App Initialization ---
app = Flask(__name__)


# --- Agent Logic ---
async def run_agent(prompt: str, model_name: str):
    """
    Initializes model, connects to MCP, creates agent, invokes it.
    Returns a dictionary containing the response or an error.
    """
    if model_name not in AVAILABLE_MODELS:
        return {"error": f"Model '{model_name}' is not available."}

    print("--- Running Agent ---")
    print(f"Model: {model_name}")
    print(f"Prompt: {prompt}")

    try:
        model = ChatOllama(model=model_name, temperature=0)

        async with MultiServerMCPClient(
            {
                "strings": {"url": STRINGS_URL, "transport": "sse"},
                "arithmetic": {"url": ARITHMETIC_URL, "transport": "sse"},
                "weather": {"url": WEATHER_URL, "transport": "sse"},
            }
        ) as client:
            print("MCP Client connected.")
            tools = client.get_tools()
            if not tools:
                print("Warning: No tools loaded from MCP client.")
                # Depending on the agent, this might be okay or an error
            else:
                print(f"Tools obtained: {[tool.name for tool in tools]}")

            agent = create_react_agent(model, tools)
            print("Agent created.")

            # Use the standard list-of-messages format for input
            invocation_input = {"messages": [HumanMessage(content=prompt)]}

            print(f"Invoking agent with input: {invocation_input}")
            result = await agent.ainvoke(invocation_input)
            print(f"Agent raw result: {result}")  # Log raw result

            # Extract final answer
            final_answer = None
            if result and "messages" in result and isinstance(result["messages"], list):
                # Find the last AIMessage with actual content
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and msg.content:
                        # Check if it's not just an empty AIMessage indicating a tool call
                        if (
                            not hasattr(msg, "tool_calls")
                            or not msg.tool_calls
                            or msg.content.strip()
                        ):
                            final_answer = msg.content
                            break  # Found the final response

            if final_answer:
                print(f"Extracted final answer: {final_answer}")
                return {"response": final_answer}
            else:
                print("Could not extract a final AIMessage response.")
                # Look for potential errors or return the last message content regardless
                last_message_content = (
                    result["messages"][-1].content
                    if result.get("messages")
                    else "Agent finished without a clear final response."
                )
                # You might want to return the full message list or a specific error here.
                # For simplicity, let's return the last message's content or a generic message.
                return {
                    "response": last_message_content
                    or "Agent did not provide a final answer."
                }

    except ConnectionRefusedError as e:
        error_msg = f"Connection Error: Could not connect to one or more MCP services ({e}). Please ensure they are running."
        print(error_msg)
        print(traceback.format_exc())  # Log stack trace
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"An unexpected error occurred during agent execution: {e}"
        print(error_msg)
        print(traceback.format_exc())  # Log stack trace for debugging
        return {"error": error_msg}


# --- Flask Routes ---
@app.route("/")
def index():
    """Serves the chat interface HTML."""
    return render_template(
        "chat.html", models=AVAILABLE_MODELS, default_model=AVAILABLE_MODELS[0]
    )


@app.route("/chat", methods=["POST"])
async def chat():
    """Handles chat messages from the frontend."""
    try:
        data = request.get_json()
        if not data or "prompt" not in data or "model" not in data:
            return jsonify({"error": "Missing 'prompt' or 'model' in request"}), 400

        prompt = data["prompt"]
        model_name = data["model"]

        # Run the async agent function
        result = await run_agent(prompt, model_name)

        # Return the result (response or error) as JSON
        return jsonify(result)

    except Exception as e:
        print(f"Error in /chat route: {e}")
        print(traceback.format_exc())
        return jsonify({"error": f"Server error: {e}"}), 500


# --- Run the App ---
if __name__ == "__main__":
    # Set host='0.0.0.0' to make it accessible on your network
    # Debug=True is helpful for development (auto-reload)
    app.run(debug=True, host="0.0.0.0", port=5000)
