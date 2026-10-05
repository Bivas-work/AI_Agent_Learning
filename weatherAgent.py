import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

resp = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=50,  # model stops after ~50 output tokens
    messages=[{"role": "user", "content": "Say hello"}],
)
print(resp.usage)  # input_tokens, output_tokens
print(resp.content[0].text)
