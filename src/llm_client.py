"""Thin wrapper around the Ollama Python client."""
import json
import ollama
from pathlib import Path

MODEL_NAME = "llama3.2:3b"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "listing_prompt.txt"


def load_prompt_template() -> str:
    """Load the prompt template from disk."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def generate_listing(category: str, raw_input: str) -> dict:
    """Send the merchant's input to the local LLM and return a parsed listing.

    The LLM detects the language and produces the structured listing in one call.

    Raises:
        ValueError: if the model returns invalid JSON.
    """
    template = load_prompt_template()
    prompt = template.format(category=category, raw_input=raw_input)

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0.3}
    )

    raw_content = response["message"]["content"]

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {raw_content[:200]}") from e


def warm_up() -> None:
    """Pre-load the model into memory to avoid cold-start latency."""
    ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": "ping"}],
        options={"num_predict": 1}
    )
