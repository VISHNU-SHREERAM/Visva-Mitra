import asyncio
import os
import argparse
from typing import List, Optional
from datetime import datetime

from mcp.client.sse import sse_client
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from getpass import getpass

# Load environment variables
load_dotenv()

# Check for Google API key
if os.environ.get("GOOGLE_API_KEY") is None:
    os.environ["GOOGLE_API_KEY"] = getpass("Enter your Google API Key: ")

# Server URLs
SERVER_URLS = {
    "strings": {"url": "http://localhost:8001/sse", "transport": "sse"},
    "arithmetic": {"url": "http://localhost:8002/sse", "transport": "sse"},
    "weather": {"url": "http://localhost:8003/sse", "transport": "sse"},
    "process": {"url": "http://localhost:8004/sse", "transport": "sse"},
}


def print_welcome_message():
    """Print welcome message and available tools."""
    print("\n" + "=" * 50)
    print("  Universal Assistant via MCP  ".center(50, "="))
    print("=" * 50)
    print("\nAvailable servers:")
    for server in SERVER_URLS.keys():
        print(f"  - {server}")
    print("\nExample commands:")
    print("  - Reverse the string 'hello world'")
    print("  - What is the product of 3 and 17?")
    print("  - What is the weather in London?")
    print("  - Show me the CPU usage on this machine")
    print("  - What processes are using the most memory?")
    print("\nType 'exit' to quit or 'servers' to see available servers and tools.")
    print("-" * 50 + "\n")


async def get_available_tools():
    """Connect to servers and list available tools."""
    try:
        async with MultiServerMCPClient(SERVER_URLS) as client:
            tools = client.get_tools()
            return {tool.name: tool.description for tool in tools}
    except Exception as e:
        print(f"Error fetching tools: {e}")
        return {}


async def interactive_session(model_name: str = "gemini-1.5-flash"):
    """Run an interactive session with the Universal Assistant."""
    print_welcome_message()

    # Initialize model
    try:
        if model_name.startswith("gemini"):
            model = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        else:
            model = ChatOllama(model=model_name, temperature=0)
    except Exception as e:
        print(f"Error initializing model: {e}")
        return

    # Main interaction loop
    running = True
    while running:
        try:
            user_input = input("👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye! 👋")
                running = False
                continue

            if user_input.lower() == "servers":
                print("\nAvailable MCP Servers and Tools:")
                tools = await get_available_tools()
                for server_name, server_info in SERVER_URLS.items():
                    print(f"\n📡 {server_name.upper()} SERVER ({server_info['url']})")
                    server_tools = {
                        name: desc
                        for name, desc in tools.items()
                        if name.startswith(server_name)
                    }
                    if server_tools:
                        for tool_name, tool_desc in server_tools.items():
                            print(f"  - {tool_name}: {tool_desc}")
                    else:
                        print("  No tools available or server is not running")
                print()
                continue

            # Process the query
            print("🤖 Assistant: Thinking...")
            async with MultiServerMCPClient(SERVER_URLS) as client:
                start_time = datetime.now()
                agent = create_react_agent(model, client.get_tools())
                response = await agent.ainvoke({"messages": user_input})

                # Print the response
                print("🤖 Assistant:")
                for m in response["messages"]:
                    print(f"  {m.content}")

                # Show processing time
                processing_time = (datetime.now() - start_time).total_seconds()
                print(f"\n(Processed in {processing_time:.2f} seconds)")
                print("-" * 50)

        except KeyboardInterrupt:
            print("\nExiting...")
            running = False
        except Exception as e:
            print(f"Error: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Universal Assistant via MCP")
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-1.5-flash",
        help="Model to use (gemini-1.5-flash or any Ollama model)",
    )
    parser.add_argument(
        "--query", type=str, help="Single query to process (non-interactive mode)"
    )

    args = parser.parse_args()

    if args.query:
        # Non-interactive mode - process a single query
        try:
            if args.model.startswith("gemini"):
                model = ChatGoogleGenerativeAI(model=args.model, temperature=0)
            else:
                model = ChatOllama(model=args.model, temperature=0)

            async with MultiServerMCPClient(SERVER_URLS) as client:
                agent = create_react_agent(model, client.get_tools())
                response = await agent.ainvoke({"messages": args.query})

                for m in response["messages"]:
                    print(m.content)
        except Exception as e:
            print(f"Error: {e}")
    else:
        # Interactive mode
        await interactive_session(model_name=args.model)


if __name__ == "__main__":
    asyncio.run(main())
