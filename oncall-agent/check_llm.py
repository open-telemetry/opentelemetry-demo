"""Check the LLM key works: list the Groq models, then make one tool-calling request.

Usage: python oncall-agent/check_llm.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).resolve().parent / ".env")

api_key = os.environ.get("GROQ_API_KEY")
model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
if not api_key:
    sys.exit("GROQ_API_KEY is empty. Paste your key into oncall-agent/.env")

client = Groq(api_key=api_key)
available = sorted(m.id for m in client.models.list().data)
if model not in available:
    sys.exit(f"Model {model!r} is not available on this key. Pick one of:\n  " + "\n  ".join(available))

tool = {
    "type": "function",
    "function": {
        "name": "query_error_rate",
        "description": "Get the current error rate (0 to 1) of a service.",
        "parameters": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
}
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Is the payment service healthy? Check its error rate."}],
    tools=[tool],
)
message = response.choices[0].message
print(f"Key works. Model: {model}")
if message.tool_calls:
    call = message.tool_calls[0].function
    print(f"Tool calling works: the model called {call.name}({call.arguments})")
else:
    print(f"WARNING: the model answered without calling the tool: {message.content}")
