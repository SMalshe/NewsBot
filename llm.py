# llm.py — provider-agnostic text completion.
#
# Active provider is chosen by the LLM_PROVIDER env var (default "openai").
# To switch back to Claude later, just set LLM_PROVIDER=anthropic — no code change.
import os

PROVIDER = os.environ.get("LLM_PROVIDER", "openai").lower()


def complete(system, user, max_tokens=1024):
    """Return the model's text response for a system + user prompt."""
    if PROVIDER == "anthropic":
        return _anthropic(system, user, max_tokens)
    return _openai(system, user, max_tokens)


def _openai(system, user, max_tokens):
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


def _anthropic(system, user, max_tokens):
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text
