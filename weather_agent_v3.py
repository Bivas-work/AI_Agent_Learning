import os, sys, json, requests
from dotenv import load_dotenv
import anthropic
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Standing instructions: sent with every API call, outside the conversation
SYSTEM_PROMPT = """You are a concise weather assistant. You help users check today's weather for a city. 
Start by asking what city the User wants to know the weather of.

Scope:
- Only answer questions about the weather. If asked about anything else, politely say you can only help with weather.

Using tools:
- Pass the city name to get_weather exactly as the user typed it. Never correct or guess spellings yourself.
- get_weather may return several matching places. If more than one place matches, list them (name and country only) and ask the user which one they mean. Do not pick one for them, even if one seems more likely.
- If the matched place's name differs from what the user typed, mention this when you answer.

Honesty:
- Only state facts that appear in the tool results. Do not add sky conditions, seasonal comparisons, or anything else the data does not contain.
- If a tool returns an error, briefly tell the user what went wrong. Never make up weather data.

Answer format:
- Keep answers to 2-3 short sentences. No headings or bullet lists.
- Use °C and km/h.
- If the precipitation probability is above 50%, suggest carrying an umbrella."""

def get_weather(city):
    # timeout: don't hang forever if the API is slow
    # raise_for_status(): turn HTTP errors (404, 500...) into exceptions instead of bad JSON
    geo_resp = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                            params={"name": city, "count": 3}, timeout=10)
    geo_resp.raise_for_status()
    geo = geo_resp.json()
    if not geo.get("results"):
        return {"error": f"City '{city}' not found"}
    places = geo["results"]
    results = []
    for place in places:
        result = {"city": place["name"], "country": place.get("country"), "searched_for": city}
        # Per-place try: one failed place records its own error instead of discarding the others
        try:
            wx_resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": place["latitude"], "longitude": place["longitude"],
                "current": "temperature_2m,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto", "forecast_days": 1,
            }, timeout=10)
            wx_resp.raise_for_status()
            wx = wx_resp.json()
            result["current"] = wx["current"]
            result["today"] = wx["daily"]
        except requests.RequestException as e:
            result["error"] = f"Weather unavailable: {e}"
        results.append(result)
    return results

GET_WEATHER_TOOL = {
  "func": get_weather,
  "schema": {
      "name": "get_weather",
      "description": "Get current conditions and today's forecast for a city.",
      "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string", "description": "City name, e.g. Kolkata"}},
        "required": ["city"],
    }
  },
}


def run_tool(tool_name, args) -> dict:
    # Never crash here: any failure becomes an {"error": ...} dict that Claude can read and react to
    func = TOOL_FUNCTIONS.get(tool_name)
    if func is None:
        return {"error": f"Unknown tool '{tool_name}'"}
    try:
        return func(**args)
    except requests.Timeout:
        return {"error": "Weather service timed out. Try again later."}
    except requests.RequestException as e:  # no internet, DNS failure, HTTP 4xx/5xx...
        return {"error": f"Network error: {e}"}
    except Exception as e:  # bad args from Claude, unexpected JSON shape, etc.
        return {"error": f"{type(e).__name__}: {e}"}


# 2. Describe the tool to Claude
ALL_TOOLS = [GET_WEATHER_TOOL]
tools = [t["schema"] for t in ALL_TOOLS]
TOOL_FUNCTIONS = {t["schema"]["name"]: t["func"] for t in ALL_TOOLS}

# 3. The agent loop
MAX_TURNS = 10  # safety cap on API calls


def log(msg):
    # Logs go to stderr: stdout must stay clean for whoever calls this agent (e.g. an MCP server)
    print(msg, file=sys.stderr)


def agent_loop(question: str) -> str:
    """Run the weather agent on one question and return its final answer as text.

    No input() here: the caller supplies the question and receives the answer.
    If the agent needs clarification (e.g. which Mumba?), that question IS the answer.
    """
    messages = [{"role": "user", "content": question}]  # local: each call starts fresh

    for _ in range(MAX_TURNS):
        # Errors from Claude's API itself can't be sent back to Claude, so report them to the caller
        try:
            resp = client.messages.create(model="claude-haiku-4-5", max_tokens=300,
                                          system=SYSTEM_PROMPT, tools=tools, messages=messages)
        except anthropic.APIConnectionError:
            return "Error: can't reach the Claude API. Check your internet connection."
        except anthropic.RateLimitError:
            return "Error: rate limited by the Claude API. Wait a bit and try again."
        except anthropic.APIStatusError as e:  # bad API key (401), server error (5xx), etc.
            return f"Error: Claude API error {e.status_code}: {e.message}"
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":  # Claude is done -> its text is the final answer
            return "".join(b.text for b in resp.content if b.type == "text")

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            log(f"[Claude called {block.name}({block.input})]")
            output = run_tool(block.name, block.input)
            failed = "error" in output
            if failed:
                log(f"[Tool error: {output['error']}]")
            # is_error tells Claude the call failed, so it can retry, ask the user, or explain
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": json.dumps(output), "is_error": failed})
        messages.append({"role": "user", "content": results})

    return f"Error: stopped after {MAX_TURNS} turns without a final answer."


def main():
    # Only the human-facing wrapper uses input(); agent_loop stays reusable
    while True:
        question = input("Ask about the weather (or 'quit'): ").strip()
        if question.lower() in ("", "quit", "exit"):
            break
        print(f"Agent: {agent_loop(question)}")


if __name__ == "__main__":
    main()