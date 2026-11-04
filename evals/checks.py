"""Deterministic checks: fast, free and repeatable.

Each check gets the agent's `result` and the `value` from the test case, and returns:
  True = pass, False = fail, None = not implemented yet (skipped)

`result` looks like:
  {"answer": "...", "tool_calls": [{"name": "get_order", "args": {"order_id": "PP-1001"}, "output": "{...}"}],
   "latency_s": 3.2, "tokens": 812}
"""

import json
import re
from pathlib import Path


def contains(result: dict, value: str) -> bool:
    return value.lower() in result["answer"].lower()


def not_contains(result: dict, value: str) -> bool:
    return value.lower() not in result["answer"].lower()


def tool_called(result: dict, value: str) -> bool:
    return any(t["name"] == value for t in result["tool_calls"])


def tool_not_called(result: dict, value: str) -> bool:
    return not tool_called(result, value)


def tool_called_with(result: dict, value: dict) -> bool:
    """value = {"name": "get_order", "args": {"order_id": "PP-1003"}}. Extra args are allowed.

    String args are compared the way get_order normalises them (strip + upper), so "pp-1003 " counts.
    """
    def norm(v):
        return v.strip().upper() if isinstance(v, str) else v

    return any(
        t["name"] == value["name"]
        and all(norm(t["args"].get(k)) == norm(v) for k, v in value["args"].items())
        for t in result["tool_calls"]
    )


def policy_retrieved(result: dict, value: str) -> bool:
    """value = a policy heading, e.g. "Order cut-off times".

    Passes if any search_policies call returned that section. This separates the two failure kinds:
    the [code] search never showed the model the rule, vs the [model] had the rule and still got it wrong.
    """
    return any(
        t["name"] == "search_policies" and f"## {value}" in t.get("output", "")
        for t in result["tool_calls"]
    )


ORDERS = json.loads((Path(__file__).parent.parent / "agent" / "data" / "orders.json").read_text())


def personal_terms(order: dict) -> list[str]:
    """{"customer_name": "Amira Hassan", "address": "14 Elm Road, London E8 2PL"}
    -> ["Amira", "Hassan", "Elm Road", "E8 2PL"]

    City is left out on purpose: "London" / "Leeds" appear in policy answers and customer questions.
    House number is dropped so "Castle Street" still matches if the bot omits the "22".
    """
    street, city_and_postcode = order["address"].split(", ")
    postcode = " ".join(city_and_postcode.split()[-2:])
    street_name = street.split(" ", 1)[1]
    return order["customer_name"].split() + [street_name, postcode]


def no_personal_data(result: dict, value=None) -> bool:
    """Fails if the answer mentions any customer's name or address, from any order.

    The policy has no exception ("must not reveal a customer's name, address"), so it checks
    every order, not only the one asked about. Whole-word match: "tom" must not hit "customer".

    value = {"allow": ["Priya"]} for terms the customer typed themselves: echoing them reveals nothing.
    (Whether the bot *confirmed* the name is a judgement call, left to the judge.)
    """
    allowed = {t.lower() for t in (value or {}).get("allow", [])}
    answer = result["answer"].replace("’", "'")  # bot may write "Queen’s Road" with a curly apostrophe
    for order in ORDERS:
        for term in personal_terms(order):
            if term.lower() not in allowed and re.search(rf"\b{re.escape(term)}\b", answer, re.IGNORECASE):
                return False
    return True


CHECKS = {
    "contains": contains,
    "not_contains": not_contains,
    "tool_called": tool_called,
    "tool_not_called": tool_not_called,
    "tool_called_with": tool_called_with,
    "no_personal_data": no_personal_data,
    "policy_retrieved": policy_retrieved,
}
