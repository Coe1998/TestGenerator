from openai import OpenAI
from generators.prompt_builder import build_prompt
from config import OPENAI_MODEL, OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def call_openai(scenarios, full_content: str, framework: str = "mstest") -> str:
    prompt = build_prompt(scenarios, full_content, framework)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content