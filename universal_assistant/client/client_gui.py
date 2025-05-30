"""GUI for the Universal Assistant using Flask and LangChain."""

import os
import time
import traceback

import mlflow
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from prefect import flow, task
from pydantic import Json

load_dotenv()

GOOGLE_API_KEY_ENV_VAR = "GOOGLE_API_KEY"
BRAVE_API_KEY_ENV_VAR = "BRAVE_API_KEY"
AVAILABLE_MODELS = [
    "qwen3:8b",
    # "qwen2.5:7b",
    # "qwen2.5:0.5b",
    "gemini-2.0-flash",
    # "gemini-2.5-pro-preview-03-25",
]
STRINGS_URL = "http://localhost:8001/sse"
ARITHMETIC_URL = "http://localhost:8002/sse"
WEATHER_URL = "http://localhost:8003/sse"
INFO_URL = "http://localhost:8004/sse"


app = Flask(__name__)


mlflow.set_tracking_uri("http://localhost:5000")


@task(name="run_agent_task", retries=1)
async def run_agent_task(prompt: str, model_name: str) -> dict:
    """Run the agent with the given prompt and model name."""
    if model_name not in AVAILABLE_MODELS:
        return {"error": f"Model '{model_name}' is not available or configured."}

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
            elif ":" in model_name:
                model = ChatOllama(model=model_name, temperature=0)
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
                            "BRAVE_API_KEY=" + os.getenv(
                                BRAVE_API_KEY_ENV_VAR, ""
                            ),
                            "mcp/brave-search",
                        ],
                        "transport": "stdio",
                    },
                    # "filesystem": {
                    #     "command": "docker",
                    #     "args": [
                    #         "run",
                    #         "-i",
                    #         "--rm",
                    #         "--mount",
                    #         "type=bind,src=C:/Users/dhruv/OneDrive/Desktop/MLOps/MCP/universal_assistant/test,dst=/project",
                    #         "mcp/filesystem",
                    #         "/project",
                    #     ],
                    #     "transport": "stdio",
                    # },
                    # "memory": {
                    #     "command": "docker",
                    #     "args": [
                    #         "run",
                    #         "-i",
                    #         "--rm",
                    #         # Mount a volume to persist memory data
                    #         "--mount",
                    #         "type=volume,src=mcp_memory_data,dst=/app/data",
                    #         # You can set environment variables if needed
                    #         "-e",
                    #         "MEMORY_SIZE=1000",  # Optional: configure memory size
                    #         "mcp/memory",  # This will be the image name
                    #     ],
                    #     "transport": "stdio",
                    # },
                },
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
                            if not is_tool_call or (
                                isinstance(msg.content, str) and msg.content.strip()
                            ):
                                final_answer = msg.content
                                break

                # Process the response to extract thinking parts if present
                has_thinking = False
                thinking_content = None
                clean_response = None

                if final_answer and "<think>" in final_answer and "</think>" in final_answer:
                    has_thinking = True
                    import re

                    # Extract the thinking part
                    thinking_match = re.search(
                        r"<think>(.*?)</think>", final_answer, re.DOTALL
                    )
                    if thinking_match:
                        thinking_content = thinking_match.group(1).strip()
                        # Remove the thinking part from the final answer
                        clean_response = re.sub(
                            r"<think>.*?</think>",
                            "",
                            final_answer,
                            flags=re.DOTALL,
                        ).strip()
                    else:
                        clean_response = final_answer
                else:
                    clean_response = final_answer

                duration = time.time() - start_time
                mlflow.log_metric("execution_time_seconds", duration)

                if final_answer:
                    mlflow.log_param("final_answer", final_answer)
                    return {
                        "response": clean_response,
                        "has_thinking": has_thinking,
                        "thinking": thinking_content if has_thinking else None,
                        "raw_response": final_answer,
                    }
                fallback = (
                    result["messages"][-1].content
                    if result.get("messages")
                    else "No answer."
                )
                mlflow.log_param("fallback_response", fallback)
                return {"response": fallback}

        except (ValueError, KeyError, RuntimeError) as e:
            error_msg = f"Unexpected error: {e}"
            mlflow.log_param("exception", error_msg)
            mlflow.log_text(traceback.format_exc(), "error_traceback.txt")
            return {"error": error_msg}


@flow
async def run_agent_flow(prompt: str, model_name: str) -> dict:
    """Flow to run the agent with the given prompt and model name."""
    return await run_agent_task(prompt, model_name)


@app.route("/")
def index() -> str:
    """Serve the main HTML page."""
    return render_template(
        "chat.html",
        models=AVAILABLE_MODELS,
        default_model=AVAILABLE_MODELS[0],
    )


@app.route("/chat", methods=["POST"])
async def chat() -> Json:
    """Handle chat messages from the frontend."""
    try:
        data = request.get_json()
        if not data or "prompt" not in data or "model" not in data:
            return jsonify({"error": "Missing 'prompt' or 'model' in request"}), 400

        prompt = data["prompt"]
        model_name = data["model"]

        result = await run_agent_flow(prompt, model_name)

        return jsonify(result)

    except (ValueError, KeyError, RuntimeError) as e:
        return jsonify({"error": f"Server error: {e}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
