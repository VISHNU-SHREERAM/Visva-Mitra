import asyncio
import os
from typing import List
from datetime import datetime

from prefect import flow, task

# from prefect.task_runners import SequentialTaskRunner
import mlflow
from mlflow.tracking import MlflowClient
import json

# from mcp import ClientSession

# from mcp.client.sse import sse_client
# from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MLflow setup
# Change default to local file-based tracking instead of port 5555
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "file:./mlruns")
EXPERIMENT_NAME = "Universal-Assistant-MCP"
USE_LOCAL_TRACKING = (
    os.environ.get("USE_LOCAL_TRACKING", "true").lower() == "true"
)  # Default to true


def setup_mlflow():
    """Set up MLflow tracking with better error handling"""
    global experiment_id

    if USE_LOCAL_TRACKING:
        logger.info("Using local MLflow tracking as specified by environment variable")
        if not os.path.exists("mlruns"):
            os.makedirs("mlruns")
        mlflow.set_tracking_uri("file:./mlruns")
        experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
        experiment_id = (
            experiment.experiment_id
            if experiment
            else mlflow.create_experiment(EXPERIMENT_NAME)
        )
        logger.info(f"MLflow tracking data saved to {os.path.abspath('mlruns')}")
        logger.info(
            "To view MLflow UI, run in a separate terminal: mlflow ui --port 5000"
        )
        return

    logger.info(f"Attempting to connect to MLflow server at {MLFLOW_TRACKING_URI}")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    try:
        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
        if experiment:
            experiment_id = experiment.experiment_id
            logger.info(f"Connected to existing experiment: {EXPERIMENT_NAME}")
        else:
            experiment_id = client.create_experiment(EXPERIMENT_NAME)
            logger.info(f"Created new experiment: {EXPERIMENT_NAME}")
    except Exception as e:
        logger.error(f"Error connecting to MLflow server: {e}")
        logger.info("Falling back to local MLflow tracking")
        if not os.path.exists("mlruns"):
            os.makedirs("mlruns")
        mlflow.set_tracking_uri("file:./mlruns")
        experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
        experiment_id = (
            experiment.experiment_id
            if experiment
            else mlflow.create_experiment(EXPERIMENT_NAME)
        )


# Initialize MLflow
setup_mlflow()

# Server URLs
SERVER_URLS = {
    "strings": {"url": "http://localhost:8001/sse", "transport": "sse"},
    "arithmetic": {"url": "http://localhost:8002/sse", "transport": "sse"},
    "weather": {"url": "http://localhost:8003/sse", "transport": "sse"},
    "process": {"url": "http://localhost:8004/sse", "transport": "sse"},
}


@task(name="connect_to_servers")
async def connect_to_servers():
    """Task to connect to all MCP servers and get available tools"""
    mlflow.log_param("server_urls", json.dumps(SERVER_URLS))

    try:
        async with MultiServerMCPClient(SERVER_URLS) as client:
            tools = client.get_tools()
            tool_names = [tool.name for tool in tools]
            mlflow.log_param("available_tools", json.dumps(tool_names))
            return True
    except Exception as e:
        mlflow.log_param("connection_error", str(e))
        return False


@task(name="initialize_llm")
def initialize_llm(model_name: str = "gemini-1.5-flash"):
    """Task to initialize the LLM"""
    mlflow.log_param("llm_model", model_name)

    try:
        if model_name.startswith("gemini"):
            if not os.environ.get("GOOGLE_API_KEY"):
                raise ValueError(
                    "GOOGLE_API_KEY environment variable is required for Google models"
                )
            model = ChatGoogleGenerativeAI(model=model_name, temperature=0)
            mlflow.log_param("llm_provider", "Google Generative AI")
        else:
            # Default to Ollama
            model = ChatOllama(model=model_name, temperature=0)
            mlflow.log_param("llm_provider", "Ollama")

        return model
    except Exception as e:
        mlflow.log_metric("llm_init_error", 1)
        mlflow.log_param("llm_error", str(e))
        raise


@task(name="process_user_query")
async def process_user_query(query: str, model, mcp_client: MultiServerMCPClient):
    """Task to process a user query using the agent"""
    mlflow.log_param("user_query", query)
    start_time = datetime.now()

    try:
        agent = create_react_agent(model, mcp_client.get_tools())
        result = await agent.ainvoke({"messages": query})

        # Log the result
        processed_result = []
        for m in result["messages"]:
            processed_result.append(m.content)

        mlflow.log_param("agent_response", json.dumps(processed_result))
        mlflow.log_metric(
            "response_time_seconds", (datetime.now() - start_time).total_seconds()
        )
        mlflow.log_metric("success", 1)

        return {"query": query, "result": processed_result, "success": True}
    except Exception as e:
        mlflow.log_metric("success", 0)
        mlflow.log_param("processing_error", str(e))
        return {"query": query, "error": str(e), "success": False}


@flow(name="universal_assistant_flow")
async def universal_assistant_flow(
    queries: List[str], model_name: str = "gemini-1.5-flash"
):
    """Main workflow for the Universal Assistant"""
    with mlflow.start_run(
        experiment_id=experiment_id,
        run_name=f"assistant-run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    ):
        # Log flow start
        mlflow.log_param("flow_start_time", datetime.now().isoformat())
        mlflow.log_param("num_queries", len(queries))

        # Initialize LLM
        model = initialize_llm(model_name)

        # Check server connections
        servers_connected = await connect_to_servers()
        if not servers_connected:
            mlflow.log_metric("flow_success", 0)
            return {"error": "Failed to connect to MCP servers"}

        # Process each query
        results = []
        async with MultiServerMCPClient(SERVER_URLS) as client:
            for i, query in enumerate(queries):
                mlflow.log_param(f"query_{i}", query)
                result = await process_user_query(query, model, client)
                results.append(result)

        # Log summary metrics
        successful_queries = sum(1 for r in results if r.get("success", False))
        mlflow.log_metric("successful_queries", successful_queries)
        mlflow.log_metric("total_queries", len(queries))
        mlflow.log_metric(
            "success_rate", successful_queries / len(queries) if queries else 0
        )
        mlflow.log_metric("flow_success", 1)

        return {
            "results": results,
            "success_rate": successful_queries / len(queries) if queries else 0,
        }


# Example of running the flow
if __name__ == "__main__":
    sample_queries = [
        "Reverse the string 'Hello, Universal Assistant!'",
        "What is 42 multiplied by 18?",
        "What's the weather like in New York?",
        "Show me the CPU usage on this machine",
        "How much memory is available on this system?",
    ]

    asyncio.run(universal_assistant_flow(sample_queries))
