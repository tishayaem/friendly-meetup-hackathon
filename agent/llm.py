import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def completion_options(client, *, json_output=False):
    """Preserve upstream Claude compatibility; validate prompted JSON locally."""
    if 'api.anthropic.com' in str(getattr(client, 'base_url', '')):
        return {}
    options = {'temperature': 0}
    if json_output:
        options['response_format'] = {'type': 'json_object'}
    return options


def client_for(role: str) -> tuple[OpenAI, str]:
    """Clients are independently configured; never print credentials."""
    client = OpenAI(
        base_url=os.environ[f"{role}_BASE_URL"],
        api_key=os.environ.get(f"{role}_API_KEY") or "not-needed",
        timeout=45,
        max_retries=0,
    )
    return client, os.environ[f"{role}_MODEL"]
