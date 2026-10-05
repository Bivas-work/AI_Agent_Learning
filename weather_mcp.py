from mcp.server.mcpserver import MCPServer
from weather_agent_v3 import agent_loop

mcp = MCPServer("weather")

@mcp.tool()
def ask_weather_agent(question: str) -> str:
    """Ask the weather agent about today's weather in a city.

    Include the full context in the question, e.g. 'Weather in Mumba, Zambia?'.
    The agent does not remember previous calls. If it asks a clarifying question
    (e.g. which of several cities), ask the user and call again with the details.
    """
    return agent_loop(question)

if __name__ == "__main__":
    mcp.run()   # talks to Claude over stdin/stdout