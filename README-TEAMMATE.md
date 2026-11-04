# Teammate setup and demo guide

Use this guide to run the implemented policy controller and evaluation suite on another computer. The original workshop README describes the starter exercise; some of its TODOs have now been implemented.

## 1. What to bring across

Clone the branch containing the implementation, or copy the complete updated project folder. **A clone only includes committed and pushed changes**; local edits and new untracked files will not appear on your teammate's computer automatically.

Check that these files arrived:

```text
agent/classifier.py
agent/demo.py
agent/policies.py
agent/verification.py
agent/data/policies.json
evals/stages.py
tests/test_pipeline.py
uv.lock
.env.example
```

Do not copy `.venv/`, `.cache/` or `__pycache__/`: recreate these locally. Create your own `.env`, rather than sharing credentials. Saved evaluation files in `results/` are optional if you want to compare previous runs.

Run every command below from the repository root, which contains `pyproject.toml`.

## 2. Requirements and machine options

| Component | Required for |
|---|---|
| [uv](https://docs.astral.sh/uv/) and Python 3.11+ | All commands; uv can install Python for you |
| Git, or a copy of the updated project | Obtaining the code |
| Internet access initially | Installing Python/dependencies and downloading models, or calling a hosted service |
| Native [Ollama](https://ollama.com/), **or** Docker with Compose, **or** a compatible hosted API | Live classification, answering and judging |
| Embedding-capable model/API | Optional semantic retrieval |

**No models, GPU, Docker or API credentials are needed for the offline tests and alias-search benchmark.**

There is no measured minimum RAM/VRAM for this implementation. Local model speed depends on model size, available memory and acceleration. The full live suite runs cases sequentially and can take substantially longer than the offline tests. The API client currently has a 45-second timeout per request and no automatic transport retries.

For a faster teammate machine, start with native Ollama. The supplied Docker configuration does not request GPU access, so do not assume it is GPU-accelerated. Hosted models avoid local inference hardware requirements and may incur API charges.

## 3. Install dependencies and verify the offline portion

These commands work in PowerShell, macOS Terminal and Linux shells once uv is installed:

```sh
uv python install 3.13
uv sync --python 3.13 --locked
uv run pytest -q
uv run python -m agent.policies
uv run python -m evals.stages
```

`uv sync` includes the `dev` dependency group, which contains pytest. Python 3.13 is a reproducible choice here; the project declares support for Python 3.11 and later.

Expected results for the current unmodified catalogue:

- 56 passing offline tests.
- 15 active policies validated/indexed.
- A benchmark report for 25, 115 and 1,015 total records: the real policies plus 10, 100 or 1,000 synthetic distractors.
- Benchmark mode explicitly labelled `lexical+aliases`. It is not a semantic-model benchmark.

No baseline model-quality score or full successful live evaluation has been established yet. These offline results do not imply that every live-model case will pass.

## 4. Configure the model roles

Create `.env` once; do not overwrite an existing configuration.

PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

macOS/Linux:

```sh
test -f .env || cp .env.example .env
```

The roles are independently configured:

| Role | Variables | Required capability |
|---|---|---|
| Classifier | `CLASSIFIER_BASE_URL`, `CLASSIFIER_API_KEY`, `CLASSIFIER_MODEL` | Chat completions with JSON-object responses |
| Agent | `AGENT_BASE_URL`, `AGENT_API_KEY`, `AGENT_MODEL` | Chat completions and tool calling |
| Judge | `JUDGE_BASE_URL`, `JUDGE_API_KEY`, `JUDGE_MODEL` | Chat completions with JSON-object responses |
| Embeddings, optional | `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL` | OpenAI-compatible embeddings endpoint |

### Option A: native Ollama

Install and start Ollama. Use `ollama serve` in a separate terminal if a server is not already running. Do not start a second server on the same port.

Download the models used by `.env.example`:

```sh
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
ollama list
```

The classifier and agent share `llama3.2:3b`; the judge uses `qwen2.5:7b`. These are two downloads, not three. The example settings are:

```dotenv
CLASSIFIER_BASE_URL=http://localhost:11434/v1
CLASSIFIER_API_KEY=
CLASSIFIER_MODEL=llama3.2:3b

AGENT_BASE_URL=http://localhost:11434/v1
AGENT_API_KEY=
AGENT_MODEL=llama3.2:3b

JUDGE_BASE_URL=http://localhost:11434/v1
JUDGE_API_KEY=
JUDGE_MODEL=qwen2.5:7b

EMBEDDING_BASE_URL=http://localhost:11434/v1
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
```

If using different installed models, change the exact model IDs in `.env`. The defaults are workshop choices, not guaranteed quality or latency targets. Leave `EMBEDDING_MODEL` empty for the first run.

### Option B: Docker Ollama

Use this instead of native Ollama; both would otherwise compete for port 11434.

```sh
docker compose up -d ollama
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull qwen2.5:7b
docker compose ps
```

Use the same `.env` settings above. Python runs on the host through uv; Docker runs only the model server. The named `ollama` volume retains downloads. Stop the service after use with `docker compose stop ollama`.

### Option C: hosted or mixed providers

For each role, supply the provider's OpenAI-compatible base URL, your API key and a supported model ID. Roles can use different providers. Check the capabilities in the table above; an OpenAI-compatible URL alone does not guarantee tool-calling or JSON-format support.

Obtain current endpoint/model details from your provider. See [provider notes](docs/providers.md), but remember to configure **CLASSIFIER** as well as AGENT and JUDGE. Keep keys in `.env`, which is ignored by Git. Local fixture questions and policy data are sent to whichever providers you configure.

## 5. Check connectivity, then try one request

```sh
uv run python -m agent.demo --check
uv run python -m agent.agent "How much is Next Day delivery?"
```

The checker requires all three configured model IDs to appear in each endpoint's model-list response. It checks availability, not generation quality or feature support. Some compatible providers restrict model listing; if that check fails, inspect the provider configuration and test a single request separately.

Inspect `answer`, `outcome`, `classification`, `events` and any `error` in the returned JSON. A printed fallback is not a successful model smoke test. A normal price answer should mention £6.50.

## 6. Run the interactive demo

```sh
uv run python -m agent.demo
```

Suggested sequence:

1. Ask `Can I send 101 ml perfume?` — retrieve the rule and prohibit it.
2. Ask `Can I send cologne?` — ask for volume.
3. Ask `Where is order PP-1003?` — require purchaser verification.
4. Enter the printed **simulated** code at the dedicated secure-demo prompt — resume the original question and show order status.
5. Ask for that order's delivery address — refuse even after verification.
6. Ask a clearly unrelated question — redirect to Parcel Pigeon support.

Use `/quit` to exit. Verification is a local demonstration, not real identity proof: no email or SMS is sent. Codes have three attempts and a five-minute expiry, and success is bound to the session and order. Restart the demo if attempts are exhausted. Model routing may still fail; record such failures rather than presenting them as expected behaviour.

The controller retains the pending verification request, not full conversational memory. For the cologne example, make the next request self-contained, such as `Can I send 101 ml cologne?`, rather than only `101 ml`.

## 7. Run evaluations and save evidence

Start small:

```sh
uv run python -m evals.run --only price-next-day --no-judge --label smoke
uv run python -m evals.run --only price-next-day --label judged-smoke
```

Then run the stages and complete suite:

```sh
uv run python -m evals.stages --classifier
uv run python -m evals.run --label teammate-baseline
uv run python -m evals.run --only privacy-address --repeat 3 --label privacy-repeat
```

- The full suite contains 30 cases, including trusted verification fixtures and scripted turns.
- `--no-judge` still uses the classifier and, where needed, the agent. It is **not offline mode**.
- The stage classifier command prints classification accuracy and harmful/injection confusion counts.
- Answer evaluations save JSONL under `results/`; these files are ignored by Git, so share them explicitly if needed.
- Evaluation exit code 0 means all executed cases passed; 1 indicates failures. Invalid CLI arguments generally exit with 2. Inspect errors rather than treating every nonzero exit as a model-quality failure.

After a change, run another label and compare actual filenames printed by the runner:

```sh
uv run python -m evals.run --label teammate-improved
uv run python -m evals.compare results/BEFORE.jsonl results/AFTER.jsonl
```

Replace the two placeholder filenames. Keep case expectations and judge configuration stable when claiming fixes. Changed cases or judge model IDs are labelled separately by the comparator. Human-review several judge explanations before trusting the scorecard.

## 8. Optional: enable semantic retrieval

The default is keyword plus reviewed-alias matching. To add embeddings:

1. Choose and install an embedding-capable model on Ollama, or configure a compatible hosted embedding endpoint.
2. Set the exact `EMBEDDING_MODEL` ID and its endpoint/key in `.env`.
3. Prepare and evaluate the semantic index:

```sh
uv run python -m agent.policies --semantic
uv run python -m evals.stages --semantic
```

Do not set a chat-only model as the embedding model. The semantic benchmark also embeds synthetic distractors: its first run can be slower and can incur hosted embedding charges. Cached embeddings live under `.cache/`; changing model identity or policy content triggers recomputation as appropriate.

When semantic retrieval is enabled, use `--semantic` when explicitly preparing the index. The plain preparation command writes a lexical index to the same default index path. Runtime requests rebuild missing embeddings, which can make the first request unexpectedly slow.

## 9. Demonstrate adding a policy and its tests

The executable source is **`agent/data/policies.json`**. Add a versioned record with reviewed aliases, applicable structured conditions and embedded example tests. The Markdown policy copies are reference documentation, not the runtime search source.

Follow the complete example in [the policy/test extension guide](docs/testing-demo.md#adding-a-policy-and-its-tests), then run:

```sh
uv run python -m agent.policies
uv run pytest -q
uv run python -m evals.stages
```

Use the semantic commands instead where applicable. New embedded examples are discovered by the offline test suite. Add a live case to `evals/cases.jsonl` when introducing a new conversational behaviour. The initial rule engine supports `eq`/`gt` conjunctions; arbitrary new condition types need implementation and tests.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Imports fail or pytest is missing | Run from repo root; use `uv sync --locked` and `uv run`, not another global Python environment. |
| Dependency lock mismatch | Confirm all updated files arrived. For an intentional dependency change, regenerate the lock with `uv sync` and share the updated `uv.lock`. |
| Connection refused | Start the chosen model server; check endpoint host, port and `/v1` suffix. |
| Port 11434 already in use | Use either native Ollama or Docker Ollama, not both. |
| Model unavailable | Compare `.env` model IDs with installed/provider model IDs; pull the missing local model. |
| Classification fails or takes around 45 seconds | Check JSON-response support, model load and inference speed. Try a smaller compatible classifier or a hosted endpoint. |
| Model-list check passes but requests fail | Availability does not prove tool/JSON compatibility or acceptable latency; inspect a single request first. |
| Judge fails | Check JUDGE configuration. `--no-judge` helps isolate the problem but does not validate answer quality. |
| Semantic indexing fails | Check the embedding endpoint/model and its credentials; leave EMBEDDING_MODEL empty to isolate lexical mode. |
| Some live cases fail | Read the saved checks, events and judge reason. Passing offline tests does not guarantee a model follows the intended flow. |
| Verification succeeds but address is refused | Expected: current privacy policy forbids disclosing names, addresses and phone numbers even after verification. |

## Handoff checklist

- Offline tests pass and the catalogue indexes.
- All three model roles are available; a single classified/answered/judged case has been inspected.
- Verification demo has been rehearsed.
- Full live results have been saved, with failures and judge disagreements identified.
- Retrieval mode is labelled honestly: aliases alone versus actual embeddings.
- A new-policy example and its tests have been rehearsed.

Previously verified on the development machine: 56 offline tests and the small lexical benchmark. The complete live suite and real embedding retrieval remain unverified there. Runtime output checks are prototype safeguards, not a guarantee against every hallucination or disclosure. See [implementation limits](docs/testing-demo.md#implemented-boundaries-and-limits).
