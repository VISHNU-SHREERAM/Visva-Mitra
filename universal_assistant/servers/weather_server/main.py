import os
import httpx
from mcp.server.fastmcp import FastMCP

# Set your OpenWeatherMap API key here
API_KEY = "030894f9d4b324bdd7057af3a4ba2462"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

mcp = FastMCP("Weather Server", host="0.0.0.0", port=8003)


def kelvin_to_celsius(k):
    return round(k - 273.15, 2)


async def fetch_weather(city: str):
    params = {
        "q": city,
        "appid": API_KEY,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(BASE_URL, params=params)
        if resp.status_code != 200:
            return None, f"Error: {resp.status_code} - {resp.text}"
        data = resp.json()
        return data, None


def format_weather(data):
    main = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    wind = data.get("wind", {})
    return (
        f"Weather in {data.get('name', 'Unknown')}:\n"
        f"  {weather.get('main', 'N/A')} - {weather.get('description', 'N/A')}\n"
        f"  Temperature: {kelvin_to_celsius(main.get('temp', 0))}°C\n"
        f"  Feels like: {kelvin_to_celsius(main.get('feels_like', 0))}°C\n"
        f"  Humidity: {main.get('humidity', 'N/A')}%\n"
        f"  Wind: {wind.get('speed', 'N/A')} m/s\n"
    )


@mcp.tool()
async def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    data, error = await fetch_weather(city)
    if error:
        return error
    return format_weather(data)


@mcp.resource("weather://{city}")
async def weather_resource(city: str) -> str:
    """Weather as a resource for a city."""
    data, error = await fetch_weather(city)
    if error:
        return error
    return format_weather(data)


@mcp.prompt()
def weather_report(city: str) -> str:
    """Prompt template for weather report."""
    return f"Generate a detailed weather report for {city}."


if __name__ == "__main__":
    mcp.run("sse")
