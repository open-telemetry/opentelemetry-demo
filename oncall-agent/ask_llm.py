"""Ask the LLM any question and print its answer.

Usage: python oncall-agent/ask_llm.py "What does an on-call engineer do?"
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).resolve().parent / ".env")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if not os.environ.get("GROQ_API_KEY"):
    sys.exit("GROQ_API_KEY is empty. Paste your key into oncall-agent/.env")

question = " ".join(sys.argv[1:]) or input("Your question: ")
model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

started = time.time()
response = Groq().chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": question}],
)
print(f"\nQuestion: {question}")
print(f"Model:    {model} (via Groq, answered in {time.time() - started:.1f}s)\n")
print(response.choices[0].message.content)
