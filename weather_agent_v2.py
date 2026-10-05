import os, json, requests
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# 1. The real tool: plain Python, no AI
def get_weather(city):
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                       params={"name": city, "count": 1}).json()
    if not geo.get("results"):
        return {"error": f"City '{city}' not found"}
    place = geo["results"][0]
    wx = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": place["latitude"], "longitude": place["longitude"],
        "current": "temperature_2m,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto", "forecast_days": 1,
    }).json()
    return {"city": place["name"], "country": place.get("country"),
            "current": wx["current"], "today": wx["daily"]}

def ask_correct_city_name():
    city = input("Which city again please? ")
    return {"city": city}

# 2. Describe the tool to Claude
tools = [{
    "name": "get_weather",
    "description": "Get current conditions and today's forecast for a city.",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string", "description": "City name, e.g. Kolkata"}},
        "required": ["city"],
    }
},
{
    "name": "ask_correct_city_name",
    "description": "Ask the user to re-type the city name if their input was incorrect, ambiguous, "
                   "or get_weather returned 'not found'. Returns the new name; then call get_weather with it.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    }
}]

# 3. The agent loop
city = input("Which city? ")
messages = [{"role": "user", "content": f"Give me a short summary of today's weather in {city}."}]

MAX_TURNS = 10  # safety cap on API calls

for _ in range(MAX_TURNS):
    resp = client.messages.create(model="claude-haiku-4-5", max_tokens=300,
                                  tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": resp.content})

    text = next((b.text for b in resp.content if b.type == "text"), None)
    if text:
        print(f"Claude: {text}")

    if resp.stop_reason != "tool_use":  # Claude replied in text -> let the user answer
        reply = input("You (or 'quit'): ").strip()
        if reply.lower() in ("", "quit", "exit"):
            break
        messages.append({"role": "user", "content": reply})
        continue

    results = []
    for block in resp.content:
        if block.type != "tool_use":
            continue
        print(f"[Claude called {block.name}({block.input})]")
        if block.name == "get_weather":
            output = get_weather(**block.input)
        elif block.name == "ask_correct_city_name":
            output = ask_correct_city_name()
        else:
            output = {"error": f"Unknown tool '{block.name}'"}
        results.append({"type": "tool_result", "tool_use_id": block.id,
                        "content": json.dumps(output)})
    messages.append({"role": "user", "content": results})
else:
    print(f"Stopped after {MAX_TURNS} turns.")
