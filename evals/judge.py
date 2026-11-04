"""LLM-as-judge: a second model grades each answer against rubric.md."""

import json
from pathlib import Path

from agent.llm import client_for

RUBRIC = (Path(__file__).parent / "rubric.md").read_text()
# Without the policy, the judge marked true facts (e.g. the £1.50/kg surcharge) as "made up" when they weren't in `expected`.
POLICY = (Path(__file__).parent.parent / "agent" / "data" / "policies.md").read_text()
# Without this, the judge called "order IDs look like PP-1001" and "I can look up your order" made up.
CAPABILITIES = (
    "The assistant has two tools: get_order (looks up an order by ID, e.g. PP-1001) and search_policies. "
    "Mentioning the PP-#### ID format or offering to look up an order is not made up."
)

# Lowest score that counts as a pass. Rubric: 4 = "correct, minor omissions", 3 = "missing something the customer needs".
PASS_MARK = 4

# Strict schema: Claude's OpenAI-compatible endpoint rejects {"type": "json_object"} but accepts json_schema.
# "reason" comes before "score" so the judge writes its justification before committing to a number.
VERDICT_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "verdict",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
            },
            "required": ["reason", "score"],
            "additionalProperties": False,
        },
    },
}


def build_messages(case: dict, result: dict) -> list[dict]:
    # The tool results are what the assistant actually saw. Without them the judge called real order dates "invented".
    tool_log = "\n".join(
        f"- {t['name']}({json.dumps(t['args'])}) returned:\n{t.get('output', '(not logged)')}" for t in result["tool_calls"]
    ) or "(none)"
    return [
        {"role": "system", "content": f"{RUBRIC}\n\n# What the assistant can do\n\n{CAPABILITIES}\n\n# Company policy\n\n{POLICY}"},
        {
            "role": "user",
            "content": (
                f"Customer question:\n{case['input']}\n\n"
                f"Expected behaviour:\n{case['expected']}\n\n"
                f"Tool calls the assistant made (facts from these are not made up):\n{tool_log}\n\n"
                f"Assistant's answer:\n{result['answer']}"
            ),
        },
    ]


def parse_verdict(text: str) -> dict:
    """A reply we can't read counts as a fail, not a skip: a silent ➖ would hide a broken judge."""
    try:
        data = json.loads(text)
        score = int(data["score"])
    except (ValueError, KeyError, TypeError):
        return {"score": None, "reason": f"unparseable judge reply: {text[:200]!r}", "passed": False}
    return {"score": score, "reason": data.get("reason", ""), "passed": score >= PASS_MARK}


def judge(case: dict, result: dict) -> dict | None:
    """Return {"score": 1-5, "passed": bool, "reason": "..."}, or None to skip."""
    if not case.get("expected"):
        return None

    client, model = client_for("JUDGE")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=build_messages(case, result),
            response_format=VERDICT_FORMAT,
            max_tokens=4096,  # room for the model's (hidden) thinking plus the JSON
        )
    except Exception as e:
        return {"score": None, "reason": f"judge error: {e}", "passed": False}
    return parse_verdict(response.choices[0].message.content or "")
