# Judge the Agent 🟡

> **Parcel Pigeon's** AI support bot goes live next week.
> Your job: prove whether it's ready, with evidence instead of vibes.

**Running the implemented version on a teammate's computer? Start with [the teammate setup and demo guide](README-TEAMMATE.md)** for dependencies, local/hosted models, configuration, tests, semantic search and demo steps. The workshop instructions below describe the original starter exercise.

## 🎯 What you'll build

- A **test set** of customer questions
- **Automatic checks** and an **AI judge** that grade every answer
- A **before/after scorecard** showing that your fix worked

## ⚙️ Setup (10 min)

You need: [Docker](https://docs.docker.com/get-docker/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
cp .env.example .env
docker compose up -d                                   # starts local LLMs
docker compose exec ollama ollama pull llama3.2:3b     # the agent (2 GB)
docker compose exec ollama ollama pull qwen2.5:7b      # the judge (5 GB)
uv run python -m agent.agent "How much is Next Day delivery?"
```

✅ You should see an answer mentioning **£6.50**.

💡 Using a hosted model (OpenAI, Gemini, Mistral…) instead? See [docs/providers.md](docs/providers.md).

## 🪜 The challenge

| Level | Goal | Time |
|---|---|---|
| 1 | Meet the agent | 15 min |
| 2 | Write the tests | 45 min |
| 3 | Build the judge | 30 min |
| 4 | Fix it and prove it | 30 min |
| ⭐ | Bonus | Any time left |

### Level 1: Meet the agent

1. Skim [agent/data/policies.md](agent/data/policies.md). This is what the bot should know.
2. Ask it a few questions with `uv run python -m agent.agent "..."`
3. Run the starter tests:
   ```bash
   uv run python -m evals.run --label baseline
   ```

✅ **Done when:** you see a scorecard. (➖ means "not scored yet". You'll fix that next.)

### Level 2: Write the tests

1. In [evals/checks.py](evals/checks.py), implement `tool_called`.
2. Add **at least one check of your own** (ideas in the file).
3. Add **15+ cases** to [evals/cases.jsonl](evals/cases.jsonl) → [how to write good cases](docs/writing-cases.md)

✅ **Done when:** 20+ cases, and no ➖ in the Checks column.

### Level 3: Build the judge

1. Complete the TODO in [evals/judge.py](evals/judge.py). The rubric is in [evals/rubric.md](evals/rubric.md).
2. Run the full suite again.
3. Read 3–4 of the judge's reasons in `results/`. Do you agree?
4. Is one score enough? A customer, a support manager and a lawyer would each judge the same answer differently. Pick the perspectives that matter to you (readability is one) and decide how to measure each: a check, the judge, or a number. There's no single right set, so be creative.

✅ **Done when:** every case with an `expected` field gets a score.

### Level 4: Fix it and prove it

1. Pick a failure. Change **one thing**: the [system prompt](agent/system_prompt.md), a [tool](agent/tools.py), or the model.
2. Re-run and compare:
   ```bash
   uv run python -m evals.run --label fix-1
   uv run python -m evals.compare results/<baseline>.jsonl results/<fix-1>.jsonl
   ```

💡 Watch for fixes that break something else. And not every fix belongs in the prompt.

✅ **Done when:** the comparison shows at least one 🟢 fixed and no 🔴 broke.

### ⭐ Bonus

Tracing, judge accuracy, model shoot-outs, red-teaming → [docs/stretch.md](docs/stretch.md)

## 🎤 Demo (3 min)

- Your scorecard **before and after**
- One **interesting failure**, and why it happened
- **Do you trust your judge?** Why or why not?
- **Which metrics did you choose**, and what did each one reveal?

## 🗂️ Project map

```
agent/                  the bot you're testing
├── agent.py            agent loop (no need to edit)
├── system_prompt.md    its instructions ← edit in Level 4
├── tools.py            get_order, search_policies
└── data/               policies + orders (the "truth")
evals/                  your work happens here
├── cases.jsonl         test cases ← Level 2
├── checks.py           deterministic checks ← Level 2
├── judge.py            LLM judge ← Level 3
├── rubric.md           judge's marking scheme
├── run.py              runs everything → results/
└── compare.py          before vs after
docs/                   short guides
results/                saved runs (one file per run)
```

## 🆘 Stuck?

| Problem | Try |
|---|---|
| Connection error | `docker compose ps` (is Ollama running?) and check `.env` |
| Too slow | `--only <case-id>`, `--no-judge`, or a hosted model |
| Model ignores tools | Normal for small models! That's a finding: put it in a test. |
| Anything else | Grab an organiser 🙋 |

## Policy controller and evaluation demo

The new runtime, policy catalogue, verification demo and stage tests are documented in [docs/testing-demo.md](docs/testing-demo.md). Start with `uv run pytest -q`, `uv run python -m agent.policies`, and `uv run python -m evals.stages`. Live model runs require the three model roles in `.env`.

The proposed [model scorecard and policy-growth A/B experiment](docs/evaluation-benchmark.md) defines success criteria, metrics, synthetic policy additions and the remaining work for a fair full-context comparison.
