from mcp.server.fastmcp import FastMCP
import asyncio

mcp = FastMCP("StringTools", host="localhost", port=8001)
@mcp.tool()
def reverse_string(text: str) -> str:
    """Reverses the given string."""
    return text[::-1]
@mcp.tool()
def count_words(text: str) -> int:
    """Counts the number of words in a sentence."""
    return len(text.split())

if __name__ == "__main__":
    mcp.run('sse')
