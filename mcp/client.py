import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from getpass import getpass
import os

load_dotenv()

if os.environ.get("GOOGLE_API_KEY") is None:
    os.environ["GOOGLE_API_KEY"] = getpass()

# model = ChatOllama(model="qwen2.5:7b", temperature=0)  # Use a model available via Ollama
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash",temperature=0)
STRINGS_URL = "http://localhost:8001/sse"
ARITHMETIC_URL = "http://localhost:8002/sse"
WEATHER_URL = "http://localhost:8003/sse"
async def main():
    async with MultiServerMCPClient({
        "strings":{
            "url":STRINGS_URL,
            "transport":"sse"
        },
        "arithmetic":{
            "url":ARITHMETIC_URL,
            "transport":"sse"
        },
        "weather":{
            "url":WEATHER_URL,
            "transport":"sse"
        }
    }) as client:
        agent = create_react_agent(model, client.get_tools())
        # Try out the tools via natural language
        msg1 = {"messages": "Reverse the string 'hello world'"}
        msg2 = {"messages": "What is the product of 3 and 17?"}
        msg3 = {"messages": "What is the weather in Palakkad?"}
        res1 = await agent.ainvoke(msg1)
        # print("Reversed string result:", res1)
        for m in res1['messages']:
            m.pretty_print()
        res2 = await agent.ainvoke(msg2)
        # print("Word count result:", res2)
        for m in res2['messages']:
            m.pretty_print()
        res3 = await agent.ainvoke(msg3)
        # print("Word count result:", res3)
        for m in res3['messages']:
            m.pretty_print()
if __name__ == "__main__":
    asyncio.run(main())