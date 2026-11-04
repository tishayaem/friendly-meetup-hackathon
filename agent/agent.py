"""Parcel Pigeon's support agent: the system you are evaluating.

Try it:  uv run python -m agent.agent "How much is Next Day delivery?"
"""

import json
import sys
import time
from pathlib import Path

from agent.llm import client_for
from agent.tools import TOOL_SCHEMAS, TOOLS

SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.md"


def run_agent(question: str, max_steps: int = 5) -> dict:
    """Answer one customer question. Returns the answer plus what happened along the way."""
    client, model = client_for("AGENT")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_FILE.read_text()},
        {"role": "user", "content": question},
    ]
    tool_calls, tokens = [], 0
    answer = "(agent gave up: too many steps)"
    start = time.perf_counter()

    for _ in range(max_steps):
        response = client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SCHEMAS
        )
        tokens += response.usage.total_tokens if response.usage else 0
        message = response.choices[0].message

        if not message.tool_calls:
            answer = message.content or ""
            break

        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                output = TOOLS[call.function.name](**args)
            except Exception as e:
                args, output = call.function.arguments, f"Tool error: {e}"
            tool_calls.append({"name": call.function.name, "args": args})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

    return {
        "answer": answer,
        "tool_calls": tool_calls,
        "latency_s": round(time.perf_counter() - start, 2),
        "tokens": tokens,
    }


if __name__ == "__main__":
    result = run_agent(" ".join(sys.argv[1:]) or "How much is Next Day delivery?")
    print(json.dumps(result, indent=2, ensure_ascii=False))
