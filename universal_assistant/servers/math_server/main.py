"""Arithmetic Server."""

from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Arithmetic Server", host="0.0.0.0", port=8002)


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    error = "Cannot divide by zero"
    if b == 0:
        raise ValueError(error)
    return a / b


@mcp.resource("help://arithmetic")
def arithmetic_help() -> str:
    """Get help on using the arithmetic server."""
    return """
    Arithmetic Server Help
    ======================

    This server provides basic arithmetic operations:

    - add(a, b): Add two numbers
    - subtract(a, b): Subtract b from a
    - multiply(a, b): Multiply two numbers
    - divide(a, b): Divide a by b (raises error if b is 0)

    Example usage:
    1. Call add(5, 3) to get 8
    2. Call subtract(10, 4) to get 6
    3. Call multiply(2, 7) to get 14
    4. Call divide(20, 5) to get 4
    """


if __name__ == "__main__":
    mcp.run("sse")
