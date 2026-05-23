"""Refinement module: third LLM call that fixes a flawed listing.

Takes the previous listing + critic's feedback, produces an improved listing
addressing the specific issues identified.
"""
import json
import ollama
from pathlib import Path

REFINER_MODEL = "llama3.2:3b"
REFINE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "refine_prompt.txt"


def load_refine_template() -> str:
    """Load the refine prompt template from disk."""
    return REFINE_PROMPT_PATH.read_text(encoding="utf-8")


def refine_listing(
    raw_input: str,
    category: str,
    language: str,
    previous_listing: dict,
    critique: dict,
) -> dict:
    """Regenerate a listing using the critic's feedback as guidance."""
    template = load_refine_template()

    issues_text = "\n".join(
        f"- {issue}" for issue in critique.get("issues", [])
    ) or "- (Critic flagged a low score but listed no specific issues. Improve completeness, language consistency, and faithfulness.)"

    prompt = template.format(
        raw_input=raw_input,
        category=category,
        language=language.upper(),
        previous_title=previous_listing.get("title", ""),
        previous_description=previous_listing.get("description", ""),
        previous_pitch=previous_listing.get("whatsapp_pitch", ""),
        previous_trust_signals=json.dumps(previous_listing.get("trust_signals", {})),
        previous_score=critique.get("total_score", 0),
        issues=issues_text,
    )

    response = ollama.chat(
        model=REFINER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0.2}
    )

    raw_content = response["message"]["content"]
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Refiner returned invalid JSON: {raw_content[:200]}") from e
