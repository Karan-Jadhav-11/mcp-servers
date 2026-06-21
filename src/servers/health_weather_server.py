# pyrefly: ignore [missing-import]
from openapi_pydantic.v3.v3_0 import response
from fastmcp import FastMCP
import asyncio, httpx, os
import logging, json, time
import threading
import urllib.request
from datetime import datetime, UTC
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# pyrefly: ignore [missing-import]
from src.security import create_auth_provider, create_security_middleware, InputSanitizer, OutputSanitizer

load_dotenv()

mcp = FastMCP("health-weather-server", auth=create_auth_provider())

# ── Security middleware stack ────────────────────────────────
for middleware in create_security_middleware():
    mcp.add_middleware(middleware)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger("mcp-server")

def log_tool_call(tool: str, duration_ms: float, success: bool):
    logger.info(json.dumps({
        "event":   "tool_call",
        "tool":    tool,
        "ms":      round(duration_ms, 2),
        "success": success,
        "ts":      datetime.now(UTC).isoformat(),
    }))


@mcp.prompt()
def weather_report(city: str, style: str = "detailed") -> str:
    """Generate a full weather report with forecast advice for a city.
    style: 'brief' | 'detailed' | 'casual'"""
    return f"""Fetch the current weather for '{city}' using the weather_tool, then write
a {style} weather report. Include: temperature, what to wear, activity suggestions,
and any weather warnings. Style: {style}."""


# Step 1: Load credential from environment ─────────────────
OWM_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# step 2: Define constrains 
OWM_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
TIMEOUT_SECS = 10
MAX_RETRIES = 2

# FastMCP: @mcp.tool() + async def + return plain string

@mcp.tool()
async def weather_tool(city: str, units: str = "metric") -> str:
    """
    Get live weather for a city from OpenWeatherMap.
    units: 'metric' (°C) or 'imperial' (°F). Use when user asks about weather.
    """
    start = time.monotonic()
    success = True
    try:
        result = await _fetch_weather(city, units)
        return result
    except Exception:
        success = False
        raise
    finally:
        log_tool_call("weather_tool", (time.monotonic()-start)*1000, success)

async def _fetch_weather(city : str, units : str = "metric" ) -> str:

    # validate API key
    if not OWM_API_KEY:
        return " ❌ OPENWEATHER_API_KEY env var not set. Add it to your .env file."

    # validate city
    try:
        city = InputSanitizer.sanitize_string(
            city, name="city", max_length=100,
            allow_pattern=r"[a-zA-Z\s\-'.,]+"
        )
    except ValueError as e:
        return f"❌ {e}"

    try:
        units = InputSanitizer.sanitize_enum(units, {"metric", "imperial"}, name="units")
    except ValueError as e:
        return f"❌ {e}"

    # ── Step 3: Make the API call with retry ─────────────────────

    params = {"q" : city, "appid":OWM_API_KEY, "units" : units}

    for attempts in range(MAX_RETRIES+1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
                response = await client.get(OWM_BASE_URL,params = params)

                if response.status_code == 401:
                    return "❌ Invalid API key. Check OPENWEATHER_API_KEY."

                elif response.status_code == 404:
                    return f"❌ City '{city}' not found. Check spelling or try a larger city."

                elif response.status_code == 429:
                    return "❌ API rate limit hit. You have 1000 free calls/day."

                response.raise_for_status()
                data = response.json()
                break

        except httpx.TimeoutException:
            if attempts == MAX_RETRIES:
                return "❌ Weather API timed out after 3 attempts. Try again later."
            await asyncio.sleep(0.5)

        except httpx.HTTPStatusError as e:
            return f"❌ API error {e.response.status_code}: {e.response.text[:200]}"

    

# ── Step 5: Format and return — plain string, no TextContent wrapper
    unit_symbol = "°C" if units == "metric" else "°F"

    weather_text = f"""🌤️  Live Weather — {data['name']}, {data['sys']['country']}
   Temperature  : {data['main']['temp']}{unit_symbol}
   Feels Like   : {data['main']['feels_like']}{unit_symbol}
   Condition    : {data['weather'][0]['description'].title()}
   Humidity     : {data['main']['humidity']}%
   Wind Speed   : {data['wind']['speed']} m/s
   Visibility   : {data.get('visibility', 'N/A')} m"""
    return OutputSanitizer.sanitize_tool_output(weather_text, source="OpenWeatherMap API")

# ════════════════════════════════════════════════════
# HEALTH TOOLS AND RESOURCES
# ════════════════════════════════════════════════════

@mcp.tool()
def calculate_bmi(weight_kg: float, height_cm: float) -> str:
    """
    Calculate Body Mass Index (BMI) from weight and height.
    Returns BMI value, category (Underweight/Normal/Overweight/Obese),
    and basic health advice. Use when user mentions weight and height.
    """
    try:
        weight_kg = InputSanitizer.sanitize_number(weight_kg, 1, 500, name="weight_kg")
        height_cm = InputSanitizer.sanitize_number(height_cm, 30, 300, name="height_cm")
    except ValueError as e:
        return f"❌ {e}"

    bmi = round(weight_kg / (height_cm / 100) ** 2, 1)

    if   bmi < 18.5: category, advice = "Underweight", "Consider consulting a nutritionist."
    elif bmi < 25.0: category, advice = "Normal weight", "You're in a healthy range! ✓"
    elif bmi < 30.0: category, advice = "Overweight",    "Diet and exercise improvements may help."
    else:            category, advice = "Obese",          "Please consult a healthcare professional."

    return f"""⚖️  BMI Calculation:
   Weight     : {weight_kg} kg
   Height     : {height_cm} cm
   BMI Score  : {bmi}
   Category   : {category}
   Advice     : {advice}"""

HEALTH_TIPS = """# Daily Health Tips

1. 💧 Drink 8 glasses of water daily
2. 😴 Sleep 7-9 hours per night
3. 🏃 Exercise at least 30 min/day
4. 🥦 Eat 5 portions of fruit/veg daily
5. 🚫 Limit processed foods and sugar
6. 🧘 Practice mindfulness or meditation
7. ☀️ Get 15-20 min of sunlight daily
"""

@mcp.resource("resource://health/tips")
def health_tips() -> str:
    """Daily health and wellness tips."""
    return HEALTH_TIPS


def _keep_alive(port: int):
    """Background task to ping the health endpoint every 10 minutes."""
    while True:
        time.sleep(600)
        try:
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=5)
            logger.info("Keep-alive ping successful")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")

# ── Step 6: Server Run ──────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    
    # Start keep-alive daemon thread
    threading.Thread(target=_keep_alive, args=(port,), daemon=True).start()
    
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=port,
    )
