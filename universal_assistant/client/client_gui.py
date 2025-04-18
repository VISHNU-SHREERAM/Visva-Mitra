import os  # Import os to access environment variables
import traceback  # Import traceback for detailed error logging

import mlflow
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request  # Import jsonify
from langchain_core.messages import (
    AIMessage,  # Import message types
    HumanMessage,
)
from langchain_google_genai import (
    ChatGoogleGenerativeAI,  # <--- Added import for Gemini
)
from langchain_mcp_adapters.client import MultiServerMCPClient

# SubprocessToolClient
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


import time  # Add this at the top with other imports

mlflow.set_tracking_uri("http://localhost:5000")


async def run_agent(prompt: str, model_name: str):
    if model_name not in AVAILABLE_MODELS:
        return {"error": f"Model '{model_name}' is not available or configured."}

    print("--- Running Agent ---")
    print(f"Model: {model_name}")
    print(f"Prompt: {prompt}")

    # Start MLflow run
    with mlflow.start_run():
        mlflow.set_experiment("Universal Assistant")
        mlflow.set_tag("model_name", model_name)
        mlflow.set_tag("run_type", "agent_inference")
        mlflow.log_param("model_name", model_name)
        mlflow.log_param("prompt", prompt)

        start_time = time.time()

        try:
            model = None

            if model_name.startswith("gemini"):
                google_api_key = os.getenv(GOOGLE_API_KEY_ENV_VAR)
                if not google_api_key:
                    error_msg = f"Google API key not found. Please set the {GOOGLE_API_KEY_ENV_VAR} environment variable."
                    mlflow.log_param("error", error_msg)
                    return {"error": error_msg}
                model = ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=google_api_key,
                    temperature=0,
                    convert_system_message_to_human=True,
                )
                print("Gemini model initialized.")
            elif ":" in model_name:
                model = ChatOllama(model=model_name, temperature=0)
                print("Ollama model initialized.")
            else:
                error_msg = f"Unsupported model type: {model_name}"
                mlflow.log_param("error", error_msg)
                return {"error": error_msg}

            async with MultiServerMCPClient(
                {
                    "strings": {"url": STRINGS_URL, "transport": "sse"},
                    "arithmetic": {"url": ARITHMETIC_URL, "transport": "sse"},
                    "weather": {"url": WEATHER_URL, "transport": "sse"},
                    "server_info": {"url": INFO_URL, "transport": "sse"},
                    "brave_search": {
                        "command": "docker",
                        "args": [
                            "run",
                            "-i",
                            "--rm",
                            "-e",
                            "BRAVE_API_KEY=BSAxGC1s-JGptZejZb7W-srU3C38tUa",
                            "mcp/brave-search",
                        ],
                        "transport": "stdio",
                    },
                }
            ) as client:
                tools = client.get_tools()
                agent = create_react_agent(model, tools)
                mlflow.log_param("agent_type", type(agent).__name__)
                invocation_input = {"messages": [HumanMessage(content=prompt)]}

                result = await agent.ainvoke(invocation_input)
                mlflow.log_text(str(result), "agent_output.txt")

                final_answer = None
                if (
                    result
                    and "messages" in result
                    and isinstance(result["messages"], list)
                ):
                    for msg in reversed(result["messages"]):
                        if isinstance(msg, AIMessage) and msg.content:
                            is_tool_call = hasattr(msg, "tool_calls") and msg.tool_calls
                            if not is_tool_call or msg.content.strip():
                                final_answer = msg.content
                                break

                duration = time.time() - start_time
                mlflow.log_metric("execution_time_seconds", duration)

                if final_answer:
                    mlflow.log_param("final_answer", final_answer)
                    return {"response": final_answer}
                else:
                    fallback = (
                        result["messages"][-1].content
                        if result.get("messages")
                        else "No answer."
                    )
                    mlflow.log_param("fallback_response", fallback)
                    return {"response": fallback}

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(error_msg)
            mlflow.log_param("exception", error_msg)
            mlflow.log_text(traceback.format_exc(), "error_traceback.txt")
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
    app.run(debug=True, host="0.0.0.0", port=5001)
