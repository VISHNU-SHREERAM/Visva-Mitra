"""Browser Control and System Monitoring MCP Server."""

from mcp.server.fastmcp import FastMCP
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from models import SearchQuery
import asyncio
import shutil
import uuid
from threading import Lock
import cv2
import psutil
import pyautogui
import base64
import os

class BrowserWindowLimitReachedError(Exception):
    """Exception raised when the browser window limit is reached."""

# Create MCP server instance
mcp = FastMCP("BrowserControl", host="0.0.0.0", port=8005)

# Global variables for browser
PLAYWRIGHT: Playwright | None = None
BROWSER: Browser | None = None
CONTEXT: BrowserContext | None = None

# Global variables for camera
CAMERA: cv2.VideoCapture | None = None
CAMERA_LOCK: Lock = Lock()

SEARCH_URL = "https://www.bing.com/search?q="
MAX_WINDOWS = 5

async def initialize_camera() -> str:
    """Initialize the camera."""
    global CAMERA
    if CAMERA is None or not CAMERA.isOpened():
        CAMERA = cv2.VideoCapture(0)
        if not CAMERA.isOpened():
            return "Error: Could not open camera."
        
        # Warm up the camera
        for _ in range(10):
            ret, _ = CAMERA.read()
            if not ret:
                return "Error: Could not warm up camera."
            await asyncio.sleep(0.1)
    return "Camera initialized successfully"

def cleanup_camera() -> None:
    """Release camera resources."""
    global CAMERA
    if CAMERA is not None:
        CAMERA.release()
        CAMERA = None

def format_size(byte_size: float) -> str:
    """Format byte size into human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if byte_size < 1024:
            return f"{byte_size:.2f}{unit}"
        byte_size /= 1024
    return f"{byte_size:.2f}PB"

def get_disk_usage() -> tuple[int, int, int]:
    """Return disk usage (total, used, free) in bytes."""
    total, used, free = shutil.disk_usage("/")
    return total, used, free

async def initialize_browser():
    """Initialize the browser on startup."""
    global PLAYWRIGHT, BROWSER, CONTEXT
    if PLAYWRIGHT is None:
        PLAYWRIGHT = await async_playwright().start()
        BROWSER = await PLAYWRIGHT.firefox.launch(headless=False)
        CONTEXT = await BROWSER.new_context()

async def cleanup_browser():
    """Cleanup browser on shutdown."""
    global PLAYWRIGHT, BROWSER, CONTEXT
    if CONTEXT:
        for page in CONTEXT.pages:
            await page.close()
    if BROWSER:
        await BROWSER.close()
    if PLAYWRIGHT:
        await PLAYWRIGHT.stop()
    PLAYWRIGHT = BROWSER = CONTEXT = None

@mcp.tool()
async def open_new_window() -> str:
    """Open a new window in the existing browser context.
    
    Limited to 5 pages by default.
    
    Returns:
        str: Response message indicating success or failure.
    """
    await initialize_browser()
    
    if CONTEXT is None:
        return "Browser context is not initialized."

    try:
        if len(CONTEXT.pages) >= MAX_WINDOWS:
            raise BrowserWindowLimitReachedError("Maximum number of browser windows reached.")
        
        await CONTEXT.new_page()
        return "Opened a new window."
    except BrowserWindowLimitReachedError as e:
        return str(e)

@mcp.tool()
async def search_web_on_browser(query: str) -> str:
    """Perform a search on the most recently opened page.

    Args:
        query: The search query to be performed.

    Returns:
        str: Response message with search results.
    """
    await initialize_browser()
    
    if CONTEXT is None:
        return "Browser context is not initialized."

    if len(CONTEXT.pages) == 0:
        # If no pages exist, open a new window automatically
        await open_new_window()

    # Get the last page in the context
    page: Page = CONTEXT.pages[-1]
    await page.goto(SEARCH_URL + query)
    try:
        results = await page.locator("h2 a").all_text_contents()
        return f"Searching for {query}. Top results are: {results[:5]}"
    except Exception as e:
        return f"Error performing search: {e!s}"

@mcp.tool()
async def new_window_and_search(query: str) -> str:
    """Open a new window and perform a search.
    
    Args:
        query: The search query to be performed.
        
    Returns:
        str: Response message with search results.
    """
    await open_new_window()
    return await search_web_on_browser(query)

@mcp.tool()
async def close_current_window() -> str:
    """Close the most recently opened window if any exist.
    
    Returns:
        str: Response message indicating success or failure.
    """
    await initialize_browser()
    
    if CONTEXT is None:
        return "Browser context is not initialized."

    if len(CONTEXT.pages) == 0:
        return "No open windows to close."

    await CONTEXT.pages[-1].close()
    return "Closed the current window."

@mcp.tool()
async def close_all_windows() -> str:
    """Close all open pages in the current context.
    
    Returns:
        str: Response message indicating success.
    """
    await initialize_browser()
    
    if CONTEXT is None:
        return "Browser context is not initialized."

    for page in CONTEXT.pages:
        await page.close()
    return "Closed all browser windows."

@mcp.tool()
async def get_window_count() -> str:
    """Get the number of currently open windows.
    
    Returns:
        str: Number of open windows.
    """
    await initialize_browser()
    
    if CONTEXT is None:
        return "Browser context is not initialized."
    
    return f"Currently {len(CONTEXT.pages)} window(s) open."
@mcp.tool()
async def close_camera() -> str:
    """Close the camera if it is open."""
    cleanup_camera()
    return "Camera closed."
@mcp.tool()
async def capture_camera() -> str:
    """Capture an image from the camera of the device and return it as a markdown image link."""
    await initialize_camera()
    
    if CAMERA is None or not CAMERA.isOpened():
        return "Error: Camera not available."
    
    # Lock the camera access to avoid race conditions
    with CAMERA_LOCK:
        for _ in range(10):
            ret, frame = CAMERA.read()
        ret, frame = CAMERA.read()
    
    if not ret:
        return "Error: Failed to capture image."
    
    try:
        # Save to client's static directory instead
        static_dir = "../../client/static/images"
        os.makedirs(static_dir, exist_ok=True)
        
        filename = f"camera_{uuid.uuid4().hex}.png"
        filepath = os.path.join(static_dir, filename)
        
        # Encode the captured frame as a PNG image in memory
        success, encoded_image = cv2.imencode(".png", frame)
        if not success:
            return "Error: Could not encode image."
        
        # Save the image to file
        with open(filepath, 'wb') as f:
            f.write(encoded_image.tobytes())
        
        # Return markdown with web URL (assuming your client serves static files)
        web_url = f"/static/images/{filename}"
        cleanup_camera()  # Cleanup camera after capture
        return f"Camera image captured!\n\n![Camera Image]({web_url})"
    except Exception as e:
        cleanup_camera()
        return f"Error capturing camera image: {e!s}"


@mcp.tool()
def take_screenshot() -> str:
    """Take a screenshot of the current screen. and return it as a markdown image link."""
    try:
        # Save to client's static directory instead
        static_dir = "../../client/static/images"
        os.makedirs(static_dir, exist_ok=True)
        
        filename = f"screenshot_{uuid.uuid4().hex}.png"
        filepath = os.path.join(static_dir, filename)
        
        image = pyautogui.screenshot()
        image.save(filepath)
        
        # Return markdown with web URL (assuming your client serves static files)
        web_url = f"/static/images/{filename}"
        return f"Screenshot saved!\n\n![Screenshot]({web_url})"
    except Exception as e:
        return f"Error taking screenshot: {e!s}"

@mcp.tool()
def get_cpu_usage() -> str:
    """Get the current CPU usage percentage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        return f"CPU usage: {cpu_percent}%"
    except Exception as e:
        return f"Error getting CPU usage: {e!s}"

@mcp.tool()
def get_disk_info() -> str:
    """Get disk usage information (total, used, free)."""
    try:
        total, used, free = get_disk_usage()
        return f"Disk usage - Total: {format_size(total)}, Used: {format_size(used)}, Free: {format_size(free)}"
    except Exception as e:
        return f"Error getting disk info: {e!s}"

@mcp.tool()
def get_ram_info() -> str:
    """Get total, used, and available RAM information."""
    try:
        total = psutil.virtual_memory().total
        available = psutil.virtual_memory().available
        used = total - available
        ram_total = format_size(total)
        ram_used = format_size(used)
        ram_available = format_size(available)
        return f"RAM usage - Total: {ram_total}, Used: {ram_used}, Available: {ram_available}"
    except Exception as e:
        return f"Error getting RAM info: {e!s}"

@mcp.tool()
def get_cpu_info() -> str:
    """Get CPU information including cores, architecture, and name."""
    try:
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        info_parts = [f"CPU cores: {cpu_count}"]
        if cpu_freq:
            info_parts.append(f"CPU frequency: {cpu_freq.current:.2f} MHz")
        
        return ", ".join(info_parts)
    except Exception as e:
        return f"Error getting CPU info: {e!s}"



if __name__ == "__main__":
    try:
        mcp.run("sse")
    finally:
        # Cleanup on exit
        cleanup_camera()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            task = loop.create_task(cleanup_browser())
        else:
            loop.run_until_complete(cleanup_browser())
