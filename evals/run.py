"""Run every test case through the agent, score it, and save a scorecard.

  uv run python -m evals.run --label baseline
  uv run python -m evals.run --only late-refund    # one case
  uv run python -m evals.run --tag rule:cut-off    # one policy rule's suite
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

ROOT = Path(__file__).parent.parent
console = Console()


def icon(passed: bool | None) -> str:
    return {True: "✅", False: "❌", None: "➖"}[passed]


def evaluate(case: dict, use_judge: bool) -> dict:
    try:
        result = run_agent(case["input"])
    except Exception as e:
        result = {"answer": "", "tool_calls": [], "latency_s": 0, "tokens": 0, "error": str(e)}
        console.print(f"[red]Agent error on {case['id']}: {e}[/red]")

    checks = []
    for check in case.get("checks", []):
        fn = CHECKS.get(check["type"])
        if fn is None:
            console.print(f"[yellow]Unknown check type '{check['type']}' in {case['id']}[/yellow]")
        checks.append({**check, "passed": fn(result, check.get("value")) if fn else None})

    verdict = judge(case, result) if use_judge else None

    # A case passes if every check (and the judge) that ran passed. Nothing ran = not scored.
    outcomes = [c["passed"] for c in checks] + [verdict["passed"] if verdict else None]
    scored = [o for o in outcomes if o is not None]
    passed = False if "error" in result else (all(scored) if scored else None)

    return {"case": case, "result": result, "checks": checks, "judge": verdict, "passed": passed}


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
    parser.add_argument("--tag", help="run only cases with this tag, e.g. rule:cut-off")
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args()

    cases = [json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
    if args.tag:
        cases = [c for c in cases if args.tag in c.get("tags", [])]

    rows = []
    for case in cases:
        with console.status(f"Running {case['id']}..."):
            rows.append(evaluate(case, use_judge=not args.no_judge))

    print_scorecard(rows)

    out = ROOT / "results" / f"{datetime.now():%Y%m%d-%H%M%S}-{args.label}.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    console.print(f"Saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
