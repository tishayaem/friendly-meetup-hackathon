# 🔌 Choosing your models

The project works with **any provider that offers an OpenAI-compatible API**. Set these in `.env`:

```bash
AGENT_BASE_URL=...   AGENT_API_KEY=...   AGENT_MODEL=...
JUDGE_BASE_URL=...   JUDGE_API_KEY=...   JUDGE_MODEL=...
```

| Provider | Base URL |
|---|---|
| Ollama (local, free) | `http://localhost:11434/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| Mistral | `https://api.mistral.ai/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter (many models, one key) | `https://openrouter.ai/api/v1` |
| Anthropic (Claude) | `https://api.anthropic.com/v1/` |

### Claude (Anthropic)

Tested with agent `claude-haiku-5-5` and judge `claude-sonnet-5-5`:

```bash
AGENT_BASE_URL=https://api.anthropic.com/v1/   AGENT_MODEL=claude-haiku-5-5
JUDGE_BASE_URL=https://api.anthropic.com/v1/   JUDGE_MODEL=claude-sonnet-5-5
```

- **No `temperature`.** Claude 4.7 and later models (including Haiku 5.5 and Sonnet 5.5) return a 400 for any value below 1. That's why `agent/agent.py` doesn't set it. Answers can vary between runs, so re-run a case before calling a fix 🟢.
- **Judge JSON:** `response_format={"type": "json_object"}` returns a 400. Use `{"type": "json_schema", "json_schema": {"name": "verdict", "strict": True, "schema": {...}}}`, or ask for JSON in the prompt and parse it.
- **Key:** use an API key that belongs to a workspace. Otherwise every request needs an `anthropic-workspace-id` header.
- Docs: [OpenAI SDK compatibility](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk)

## Tips

- The **agent** model must support **tool calling**.
- The **judge** works best as a **different, stronger** model than the agent.
- Mixing is fine: e.g. a local agent with a hosted judge.
- **Local and slow?** On a Mac, Docker can't use the GPU. A hosted model, or Ollama's native app, will be much faster.
- **Never commit `.env`.** It's already in `.gitignore`.
