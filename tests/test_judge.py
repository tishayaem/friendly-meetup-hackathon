"""Run with:  uv run --with pytest python -m pytest tests/"""

from evals.judge import PASS_MARK, build_messages, parse_verdict

CASE = {"input": "Where is PP-1003?", "expected": "In transit, due 9 November."}
RESULT = {"answer": "It's in transit.", "tool_calls": []}


def test_parse_verdict_reads_score_and_reason():
    verdict = parse_verdict('{"reason": "Correct.", "score": 5}')
    assert verdict == {"score": 5, "reason": "Correct.", "passed": True}


def test_score_at_pass_mark_passes_and_below_fails():
    assert parse_verdict(f'{{"reason": "x", "score": {PASS_MARK}}}')["passed"] is True
    assert parse_verdict(f'{{"reason": "x", "score": {PASS_MARK - 1}}}')["passed"] is False


def test_unparseable_reply_fails_loudly_instead_of_skipping():
    verdict = parse_verdict("Sure! The score is 4.")
    assert verdict["passed"] is False
    assert verdict["score"] is None
    assert "unparseable" in verdict["reason"]


def test_prompt_contains_question_expected_and_answer():
    text = "\n".join(m["content"] for m in build_messages(CASE, RESULT))
    for part in [CASE["input"], CASE["expected"], RESULT["answer"]]:
        assert part in text
