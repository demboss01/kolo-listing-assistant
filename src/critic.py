"""Self-critique module: a second LLM evaluates the first LLM's output."""
import json
import ollama
from pathlib import Path

CRITIC_MODEL = "llama3.2:3b"
CRITIQUE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "critique_prompt.txt"
PASS_THRESHOLD = 10  # Out of 12 max (6 criteria × 2 points each)


def load_critique_template() -> str:
    """Load the critique prompt template from disk."""
    return CRITIQUE_PROMPT_PATH.read_text(encoding="utf-8")


def critique_listing(raw_input: str, listing: dict, language: str = "english") -> dict:
    """Evaluate a generated listing against the original input.

    Args:
        raw_input: The merchant's original raw description.
        listing: The structured listing produced by generate_listing().
        language: The expected output language ('english' or 'french').

    Returns:
        dict with criterion scores, total_score, issues, verdict.
    """
    template = load_critique_template()
    prompt = template.format(
        raw_input=raw_input,
        title=listing.get("title", ""),
        description=listing.get("description", ""),
        whatsapp_pitch=listing.get("whatsapp_pitch", ""),
        trust_signals=json.dumps(listing.get("trust_signals", {})),
        language=language.upper(),
    )

    response = ollama.chat(
        model=CRITIC_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0.1}
    )

    raw_content = response["message"]["content"]
    try:
        critique = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Critic returned invalid JSON: {raw_content[:200]}") from e

    return critique


def needs_refinement(critique: dict) -> bool:
    """Returns True if the total score is below the pass threshold.

    We trust the deterministic Python arithmetic, not the LLM's verdict field,
    because smaller LLMs can produce a verdict that contradicts the score they
    just computed (e.g. score 9/12 but verdict 'PASS').
    """
    return critique.get("total_score", 0) < PASS_THRESHOLD
