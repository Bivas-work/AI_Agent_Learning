from openai import OpenAI
import os
from dotenv import load_dotenv


load_dotenv()
client = OpenAI(api_key=os.environ["ANTHROPIC_API_KEY"],
                base_url="https://api.anthropic.com/v1/", )


# Define the conversation messages
conversation_messages = [
    {"role": "system", "content": "You are a helpful event management assistant."},
    {"role": "user", "content": "What are some good conversation starters at networking events?"}
]

def get_response(prompt) -> str:
    conversation_messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model="claude-haiku-5-5",
        messages=conversation_messages
    )
    return response.choices[0].message.content


# Test the function with your prompt
response = get_response(conversation_messages)
print(response)