"""Run every test case through the agent, score it, and save a scorecard.

  uv run python -m evals.run --label baseline
  uv run python -m evals.run --only late-refund    # one case
  uv run python -m evals.run --no-judge            # checks only (faster)
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from agent.agent import run_agent
from evals.checks import CHECKS
from evals.judge import judge
from agent.verification import Session
from agent.policies import digest

ROOT = Path(__file__).parent.parent
console = Console()


def icon(passed: bool | None) -> str:
    return {True: "✅", False: "❌", None: "➖"}[passed]


def evaluate(case: dict, use_judge: bool) -> dict:
    try:
        session = Session()
        context = case.get('context', {})
        if context.get('verified_order'):
            # Trusted evaluation fixture only, never customer-provided text.
            code = session.start(context['verified_order'])
            session.verify(code)
        turns = []
        for step in case.get('steps', [{'input':case['input']}]):
            if 'verify_order' in step:
                code = session.start(step['verify_order'])
                session.verify(code if step.get('success', True) else 'invalid')
            else:
                turns.append(run_agent(step['input'], session=session))
        result = turns[-1]
        result['turn_outcomes'] = [t.get('outcome') for t in turns]
    except Exception as e:
        result = {"answer": "", "tool_calls": [], "latency_s": 0, "tokens": 0, "error": str(e)}
        console.print(f"[red]Agent error on {case['id']}: {e}[/red]")

    checks = []
    for check in case.get("checks", []):
        fn = CHECKS.get(check["type"])
        if fn is None:
            console.print(f"[yellow]Unknown check type '{check['type']}' in {case['id']}[/yellow]")
        try:
            checks.append({**check, "passed": fn(result, check.get("value")) if fn else False})
        except Exception:
            checks.append({**check, 'passed':False, 'error':'check_failed'})

    try:
        verdict = judge(case, result) if use_judge else None
    except Exception:
        verdict = {'score':0,'passed':False,'reason':'Judge unavailable or invalid verdict','error':True}

    # A case passes if every check (and the judge) that ran passed. Nothing ran = not scored.
    outcomes = [c["passed"] for c in checks] + [verdict["passed"] if verdict else None]
    scored = [o for o in outcomes if o is not None]
    passed = False if "error" in result else (all(scored) if scored else None)

    return {"case": case, "case_hash":digest(case), "result": result, "checks": checks, "judge": verdict, "passed": passed}


def print_scorecard(rows: list[dict]) -> None:
    table = Table(title="Scorecard")
    for column in ["Case", "Pass", "Checks", "Judge", "Tools used", "Secs"]:
        table.add_column(column)
    for row in rows:
        verdict = row["judge"]
        table.add_row(
            row["case"]["id"],
            icon(row["passed"]),
            " ".join(icon(c["passed"]) for c in row["checks"]) or "-",
            f"{verdict['score']}/5" if verdict else "-",
            ", ".join(t["name"] for t in row["result"]["tool_calls"]) or "-",
            str(row["result"]["latency_s"]),
        )
    console.print(table)

    scored = [r for r in rows if r["passed"] is not None]
    passes = sum(r["passed"] for r in scored)
    by_tag = defaultdict(list)
    for r in scored:
        for tag in r["case"].get("tags", []):
            by_tag[tag].append(r["passed"])

    console.print(f"[bold]Pass rate: {passes}/{len(scored)}[/bold]  (not scored: {len(rows) - len(scored)})")
    console.print("By tag: " + ", ".join(f"{t} {sum(v)}/{len(v)}" for t, v in sorted(by_tag.items())))
    console.print(
        f"Avg latency: {sum(r['result']['latency_s'] for r in rows) / len(rows):.1f}s  "
        f"Total tokens: {sum(r['result']['tokens'] for r in rows)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run", help="name for this run, e.g. baseline")
    parser.add_argument("--cases", default=ROOT / "evals" / "cases.jsonl", type=Path)
    parser.add_argument("--only", help="run a single case by id")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument('--repeat',type=int,default=1)
    args = parser.parse_args()
    if not args.label.replace('-','').replace('_','').isalnum():
        parser.error('Label must contain only letters, digits, hyphens and underscores')

    cases = [json.loads(line) for line in args.cases.read_text(encoding='utf-8').splitlines() if line.strip()]
    validate_cases(cases)
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]

    if not cases or args.repeat < 1:
        parser.error('Select at least one case and a positive repeat count')

    rows = []
    for repetition in range(args.repeat):
        for case in cases:
            with console.status(f"Running {case['id']}..."):
                row = evaluate(case, use_judge=not args.no_judge)
                row['repetition'] = repetition + 1
                rows.append(row)

    print_scorecard(rows)

    out = ROOT / "results" / f"{datetime.now():%Y%m%d-%H%M%S}-{args.label}.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    console.print(f"Saved: {out.relative_to(ROOT)}")
    raise SystemExit(0 if all(r['passed'] is True for r in rows) else 1)


def validate_cases(cases):
    seen = set()
    for case in cases:
        if not all(k in case for k in ['id','input','expected','checks']):
            raise ValueError('Missing case fields')
        if case['id'] in seen:
            raise ValueError('Duplicate case ID')
        seen.add(case['id'])
        if any(c['type'] not in CHECKS for c in case['checks']):
            raise ValueError('Unknown check type')
        if case.get('steps') and not any('input' in s for s in case['steps']):
            raise ValueError('Conversation requires at least one customer turn')


if __name__ == "__main__":
    main()
