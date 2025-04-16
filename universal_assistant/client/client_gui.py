import os  # Import os to access environment variables
import traceback  # Import traceback for detailed error logging

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request  # Import jsonify
from langchain_core.messages import AIMessage, HumanMessage  # Import message types
from langchain_google_genai import (
    ChatGoogleGenerativeAI,  # <--- Added import for Gemini
)
from langchain_mcp_adapters.client import MultiServerMCPClient

# Import necessary model classes
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file

# --- IMPORTANT SECURITY NOTE ---
# DO NOT HARDCODE YOUR API KEY HERE.
# Set your Google API key in your .env file like this:
# GOOGLE_API_KEY=AIzaSy...your...actual...key...
GOOGLE_API_KEY_ENV_VAR = "GOOGLE_API_KEY"  # Environment variable name

# Add Gemini models to the available list
AVAILABLE_MODELS = [
    "qwen2.5:7b",
    "qwen2.5:0.5b",
    "gemini-2.0-flash",  # Example Gemini model
    "gemini-2.5-pro-preview-03-25",  # Another example Gemini model
]
STRINGS_URL = "http://localhost:8001/sse"
ARITHMETIC_URL = "http://localhost:8002/sse"
WEATHER_URL = "http://localhost:8003/sse"
INFO_URL = "http://localhost:8004/sse"  # Example URL for the info server

# --- Flask App Initialization ---
app = Flask(__name__)


# --- Agent Logic ---
async def run_agent(prompt: str, model_name: str):
    """
    Initializes the selected model (Ollama or Gemini), connects to MCP,
    creates agent, invokes it.
    Returns a dictionary containing the response or an error.
    """
    if model_name not in AVAILABLE_MODELS:
        return {"error": f"Model '{model_name}' is not available or configured."}

    print("--- Running Agent ---")
    print(f"Model: {model_name}")
    print(f"Prompt: {prompt}")

    try:
        model = None  # Initialize model variable

        # --- Model Initialization Logic ---
        if model_name.startswith("gemini"):
            print(f"Initializing Google Gemini model: {model_name}")
            google_api_key = os.getenv(GOOGLE_API_KEY_ENV_VAR)
            if not google_api_key:
                error_msg = f"Google API key not found. Please set the {GOOGLE_API_KEY_ENV_VAR} environment variable."
                print(f"ERROR: {error_msg}")
                return {"error": error_msg}
            try:
                # Ensure you have langchain-google-genai installed:
                # pip install langchain-google-genai
                model = ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=google_api_key,
                    temperature=0,
                    convert_system_message_to_human=True,  # Often helpful for ReAct agents with Gemini
                )
                print("Gemini model initialized successfully.")
            except Exception as e:
                error_msg = f"Failed to initialize Gemini model: {e}"
                print(f"ERROR: {error_msg}")
                print(traceback.format_exc())
                return {"error": error_msg}

        # Check if it's a known Ollama model (or add more types later if needed)
        elif ":" in model_name:  # Simple check for Ollama's typical naming convention
            print(f"Initializing Ollama model: {model_name}")
            try:
                model = ChatOllama(model=model_name, temperature=0)
                print("Ollama model initialized successfully.")
            except Exception as e:
                # Catch potential errors if Ollama server isn't running etc.
                error_msg = f"Failed to initialize Ollama model '{model_name}': {e}. Is Ollama running?"
                print(f"ERROR: {error_msg}")
                print(traceback.format_exc())
                return {"error": error_msg}
        else:
            # This case should ideally be caught by the initial check, but belt-and-suspenders
            error_msg = f"Model type for '{model_name}' could not be determined or is not supported."
            print(f"ERROR: {error_msg}")
            return {"error": error_msg}

        # --- MCP Client and Agent Execution (Remains the same) ---
        async with MultiServerMCPClient(
            {
                "strings": {"url": STRINGS_URL, "transport": "sse"},
                "arithmetic": {"url": ARITHMETIC_URL, "transport": "sse"},
                "weather": {"url": WEATHER_URL, "transport": "sse"},
                "server_info": {"url": INFO_URL, "transport": "sse"},
            }
        ) as client:
            print("MCP Client connected.")
            tools = client.get_tools()
            if not tools:
                print("Warning: No tools loaded from MCP client.")
                # Depending on the agent, this might be okay or an error
            else:
                print(f"Tools obtained: {[tool.name for tool in tools]}")

            # Pass the initialized model (either Ollama or Gemini)
            agent = create_react_agent(model, tools)
            print("Agent created.")

            # Use the standard list-of-messages format for input
            invocation_input = {"messages": [HumanMessage(content=prompt)]}

            print(f"Invoking agent with input: {invocation_input}")
            result = await agent.ainvoke(invocation_input)
            print(f"Agent raw result: {result}")  # Log raw result

            # --- Result Extraction (Remains the same) ---
            final_answer = None
            if result and "messages" in result and isinstance(result["messages"], list):
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and msg.content:
                        # Check if it's not just an empty AIMessage indicating a tool call
                        is_tool_call_indicator = (
                            hasattr(msg, "tool_calls") and msg.tool_calls
                        )
                        if not is_tool_call_indicator or msg.content.strip():
                            final_answer = msg.content
                            break  # Found the final response

            if final_answer:
                print(f"Extracted final answer: {final_answer}")
                return {"response": final_answer}
            else:
                print("Could not extract a final AIMessage response.")
                last_message_content = (
                    result["messages"][-1].content
                    if result.get("messages")
                    else "Agent finished without a clear final response."
                )
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


# --- Flask Routes (No changes needed here) ---
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

        # Run the async agent function (which now handles both model types)
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
