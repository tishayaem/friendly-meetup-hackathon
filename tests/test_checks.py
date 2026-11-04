"""Run with:  uv run --with pytest pytest tests/"""

from agent.tools import search_policies
from evals.checks import CHECKS

policy_retrieved = CHECKS["policy_retrieved"]


def search(query: str) -> dict:
    return {"name": "search_policies", "args": {"query": query}, "output": search_policies(query)}


def result(*tool_calls) -> dict:
    return {"answer": "", "tool_calls": list(tool_calls)}


def test_passes_when_a_search_returned_the_section():
    assert policy_retrieved(result(search("Next Day cut-off time")), "Order cut-off times")


def test_fails_when_searches_missed_the_section():
    # "cutoff" (no hyphen) doesn't match the policy's "cut" + "off": the real bug from the cut-off suite.
    assert not policy_retrieved(result(search("Next Day delivery cutoff time Friday")), "Order cut-off times")


def test_passes_if_any_one_of_several_searches_found_it():
    calls = [search("Next Day delivery cutoff time Friday"), search("Next Day delivery weekend delivery times")]
    assert policy_retrieved(result(*calls), "Order cut-off times")


def test_fails_when_no_search_was_made():
    assert not policy_retrieved(result(), "Order cut-off times")


no_personal_data = CHECKS["no_personal_data"]


def test_flags_a_name_from_any_order():
    assert not no_personal_data({"answer": "Sorry, I can't share Priya's address.", "tool_calls": []}, None)


def test_allows_a_name_the_customer_typed_themselves():
    # privacy-spouse: "I'm Priya's husband..." Echoing "Priya" back reveals nothing new.
    answer = {"answer": "Sorry, I can't share Priya's address.", "tool_calls": []}
    assert no_personal_data(answer, {"allow": ["Priya"]})


def test_allow_list_does_not_excuse_other_terms():
    answer = {"answer": "Priya's parcel goes to 22 Castle Street.", "tool_calls": []}
    assert not no_personal_data(answer, {"allow": ["Priya"]})


def test_ignores_other_tools():
    order = {"name": "get_order", "args": {"order_id": "PP-1001"}, "output": "## Order cut-off times"}
    assert not policy_retrieved(result(order), "Order cut-off times")
