import psutil
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Process Server", host="0.0.0.0", port=8004)


@mcp.tool()
def get_cpu_info() -> dict:
    """Get CPU information including usage percentage and count"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_physical_count": psutil.cpu_count(logical=False),
    }


@mcp.tool()
def get_memory_info() -> dict:
    """Get memory usage information"""
    mem = psutil.virtual_memory()
    return {
        "total": f"{mem.total / (1024**3):.2f} GB",
        "available": f"{mem.available / (1024**3):.2f} GB",
        "percent_used": mem.percent,
        "used": f"{mem.used / (1024**3):.2f} GB",
    }


@mcp.tool()
def get_disk_info() -> dict:
    """Get disk usage information"""
    disk = psutil.disk_usage("/")
    return {
        "total": f"{disk.total / (1024**3):.2f} GB",
        "used": f"{disk.used / (1024**3):.2f} GB",
        "free": f"{disk.free / (1024**3):.2f} GB",
        "percent_used": disk.percent,
    }


@mcp.tool()
def list_running_processes(limit: int = 10) -> list:
    """List the top running processes by memory usage"""
    processes = []
    for proc in sorted(
        psutil.process_iter(["pid", "name", "memory_percent"]),
        key=lambda x: x.info["memory_percent"],
        reverse=True,
    )[:limit]:
        processes.append(
            {
                "pid": proc.info["pid"],
                "name": proc.info["name"],
                "memory_percent": f"{proc.info['memory_percent']:.2f}%",
            }
        )
    return processes


@mcp.resource("help://process")
def process_help() -> str:
    """Get help on using the process server"""
    return """
    Process Server Help
    ==================
    
    This server provides system information tools:
    
    - get_cpu_info(): Get CPU usage and count information
    - get_memory_info(): Get memory usage information
    - get_disk_info(): Get disk usage information
    - list_running_processes(limit=10): List top running processes by memory usage
    
    Example usage:
    1. Call get_cpu_info() to get CPU statistics
    2. Call get_memory_info() to get memory statistics
    3. Call get_disk_info() to get disk usage statistics
    4. Call list_running_processes(5) to list the top 5 memory-consuming processes
    """


if __name__ == "__main__":
    mcp.run("sse")
