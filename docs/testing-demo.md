# Running the policy evaluation demo

The executable catalogue is `agent/data/policies.json`. The two Markdown policy copies are workshop reference documents; the controller indexes JSON only. Preserve their human-readable history, but do not retrieve retired/struck-through rules. When changing policy meaning, update the catalogue and reference documentation together.

## Setup

```powershell
Copy-Item .env.example .env  # only if .env does not already exist
uv sync
# Use an existing Ollama server, or the original Docker setup.
# Pull the agent and judge models listed in .env when they are not installed.
uv run python -m agent.demo --check
uv run python -m agent.policies
uv run pytest -q
uv run python -m evals.stages
uv run python -m agent.demo
```

Configure CLASSIFIER, AGENT and JUDGE independently in `.env`. The defaults use the workshop models. The checker reports a missing endpoint/model without printing credentials. No real identity messages are sent: the terminal prints a **simulated** code through a tester-facing channel. Enter it at the dedicated code prompt, never in the customer question. Three attempts, five-minute expiry, session/order-bound success. Names, addresses and phone numbers remain forbidden after success.

## Live evaluations

```powershell
uv run python -m evals.stages --classifier
uv run python -m evals.run --label controller
uv run python -m evals.run --only privacy-address --repeat 3 --label privacy-repeat
uv run python -m evals.compare results/BEFORE.jsonl results/AFTER.jsonl
```

There are 30 reviewed conversation/answer cases. `--no-judge` deliberately skips semantic quality judging, not hard checks. Missing/invalid required judges fail. Exit code 0 means every executed case passed; 1 means a failure; configuration errors are reported before model execution. Unknown checks and duplicate IDs are invalid. Results retain decision events, tool success/denial, case hashes, policy/prompt hashes and repetition IDs. Comparator labels changed expectations or judge models instead of calling them fixes. Do not compare single-turn raw-agent expectations to new verification expectations as if they were identical cases.

The original baseline was not captured before implementation because the required model configuration was absent. Git retains the original code; no before/after improvement is claimed yet. Use identical reviewed cases and scoring configuration for a meaningful future comparison.

## Adding a policy and its tests

Add a record to the JSON array with `id`, positive integer `version`, `active`, `topic`, `text`, reviewed `aliases` and `tests`. For executable item conditions, add a `rule`:

```json
{
  "id": "example-synthetic-liquid",
  "version": 1,
  "active": true,
  "topic": "prohibited_items",
  "text": "SYNTHETIC DEMO ONLY: example liquid over 20 ml is prohibited.",
  "aliases": ["example liquid"],
  "rule": {
    "required": ["volume_ml"],
    "conditions": [{"field": "volume_ml", "op": "gt", "value": 20}],
    "outcome": "prohibited"
  },
  "tests": [
    {"query": "Can I send 21 ml example liquid?", "facts": {"volume_ml": 21}, "expected": "prohibited"},
    {"query": "Can I send 20 ml example liquid?", "facts": {"volume_ml": 20}, "expected": "not_prohibited_by_rule"},
    {"query": "Can I send example liquid?", "facts": {}, "expected": "needs_information"}
  ]
}
```

This is not a real company policy: remove it after demonstration. Add a synonym example and a confusing non-match in the Python tests. Run index preparation, pytest and the stage benchmark again: record-level tests are discovered automatically without another evaluator. Add a live case in `evals/cases.jsonl` when the policy introduces a new conversational behaviour. Review expected outcomes independently; model-generated expectations are not an oracle.

The initial rule vocabulary supports conjunctions of `eq` and `gt`, required facts and explicit outcomes. New operators require code and unit tests. Only `volume_ml` and `standalone` have conservative input extractors; other facts need a trusted extractor or clarification. Do not imply arbitrary prose policies become executable automatically.

## Semantic indexing and growth

Set `EMBEDDING_MODEL` and its OpenAI-compatible endpoint in `.env`; use a locally installed embedding-capable model. Then:

```powershell
uv run python -m agent.policies --semantic
uv run python -m evals.stages --semantic
```

Without that setting, retrieval is explicitly **lexical + reviewed aliases**, not embeddings. Embeddings are cached by record hash and model identity; updates re-embed changed records and removed records disappear from the next index. Only active records are searchable. Similarity retrieves candidates, never decides prohibition. Exact reviewed aliases can trigger deterministic decisions; unresolved semantic matches need clarification/model explanation and remain subject to live evaluation.

The stage benchmark measures Recall@5 and rule accuracy on catalogue examples with 10, 100 and 1,000 synthetic distractors, reporting total records and latency. Semantic mode embeds distractors too. This small synthetic benchmark is not proof of production scale or hard-negative retrieval quality. Add realistic confusing neighbours and human-labelled paraphrases before making stronger claims. Run the entire cheap suite on policy changes: cross-policy retrieval interference can affect otherwise unchanged cases.

## Implemented boundaries and limits

Input classification is one model call, not a security oracle. Tools enforce authorisation regardless of suggested tool names. Refunds use deterministic templates; known prohibited-item aliases use explicit rule outcomes. General answers use at most two generation attempts and bounded tool-call loops.

Runtime output checks detect known personal-data strings, unsupported numeric claims and some false action assertions. They do **not** prove semantic grounding or catch every paraphrase/partial disclosure. The offline judge and adversarial cases measure those gaps; do not present this prototype as a complete hallucination prevention system. Classification may also over-refuse mixed requests; those should be expanded as regression cases.

The current interface retains the pending verification question, not a general multi-turn conversational memory. Evaluation supports scripted customer turns and trusted verification events, but each customer turn is otherwise self-contained. Real authentication, a secure web UI, production storage, regional holiday integration and automated arbitrary policy compilation are outside this demo.
