"""Deterministic checks: fast, free and repeatable.

Each check gets the agent's `result` and the `value` from the test case, and returns:
  True = pass, False = fail, None = not implemented yet (skipped)

`result` looks like:
  {"answer": "...", "tool_calls": [{"name": "get_order", "args": {"order_id": "PP-1001"}}],
   "latency_s": 3.2, "tokens": 812}
"""


def contains(result: dict, value: str) -> bool:
    return value.lower() in result["answer"].lower()


def not_contains(result: dict, value: str) -> bool:
    return value.lower() not in result["answer"].lower()


def tool_called(result: dict, value: str) -> bool | None:
    return any(t['name'] == value and t.get('status', 'succeeded') == 'succeeded' for t in result['tool_calls'])


def tool_called_with(result, value):
    return any(t['name'] == value['name'] and t['args'] == value['args'] and t.get('status','succeeded') == 'succeeded' for t in result['tool_calls'])


def outcome(result, value):
    return result.get('outcome') == value


def no_tool(result, value):
    return not any(t['name'] == value and t.get('status','succeeded') == 'succeeded' for t in result['tool_calls'])


def retrieved(result, value):
    return set(value) <= set(result.get('policy_ids', []))


# TODO (Level 2): add your own checks here, then register them below. Ideas:
#   tool_called_with  the right tool AND the right arguments (e.g. the correct order ID)
#   max_seconds       answer arrived in time
#   max_words         answer is concise
#   no_tools          agent didn't call any tool (e.g. for off-topic questions)
#   matches_regex     e.g. any price in the form £0.00


CHECKS = {
    "contains": contains,
    "not_contains": not_contains,
    "tool_called": tool_called,
    "tool_called_with": tool_called_with,
    "outcome": outcome,
    "no_tool": no_tool,
    "retrieved": retrieved,
}
