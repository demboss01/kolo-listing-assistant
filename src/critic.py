"""Self-critique module: a second LLM evaluates the first LLM's output."""
import json
import ollama
from pathlib import Path

CRITIC_MODEL = "llama3.2:3b"
CRITIQUE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "critique_prompt.txt"
PASS_THRESHOLD = 10  # Out of 12 max (6 criteria × 2 points each)

CRITIC_CRITERIA = [
    "faithfulness",
    "completeness",
    "language_consistency",
    "format_quality",
    "tone_appropriateness",
    "title_quality",
]

# Human-friendly names + what a perfect score means vs what a deduction means
CRITERION_DESCRIPTIONS = {
    "faithfulness": {
        "good": "uses only facts from the input",
        "weak": "may contain invented details not in the input",
        "bad":  "contains fabricated information not in the input",
    },
    "completeness": {
        "good": "includes all key facts (price, condition, accessories) in the pitch",
        "weak": "is missing one key fact from the pitch",
        "bad":  "is missing multiple key facts from the pitch",
    },
    "language_consistency": {
        "good": "all fields are in the requested language",
        "weak": "one field has wrong-language content",
        "bad":  "multiple fields are in the wrong language",
    },
    "format_quality": {
        "good": "formatting is clean (no placeholders, consistent currency)",
        "weak": "has minor formatting issues",
        "bad":  "contains placeholder tokens like [non précisé] or broken formatting",
    },
    "tone_appropriateness": {
        "good": "tone matches a product/service framing correctly",
        "weak": "tone is slightly awkward for the type of listing",
        "bad":  "tone is wrong for the type of listing (e.g. service framed as product)",
    },
    "title_quality": {
        "good": "title is concise, descriptive, and price-free",
        "weak": "title is awkwardly long or includes extra info",
        "bad":  "title is poorly formatted or includes the price",
    },
}

CRITERION_LABELS = {
    "faithfulness": "Faithfulness",
    "completeness": "Completeness",
    "language_consistency": "Language consistency",
    "format_quality": "Format quality",
    "tone_appropriateness": "Tone appropriateness",
    "title_quality": "Title quality",
}


def load_critique_template() -> str:
    """Load the critique prompt template from disk."""
    return CRITIQUE_PROMPT_PATH.read_text(encoding="utf-8")


def _recompute_total(critique: dict) -> int:
    """Sum the six criterion scores deterministically in Python."""
    return sum(int(critique.get(crit, 0) or 0) for crit in CRITIC_CRITERIA)


def summarize_critique(critique: dict) -> dict:
    """Generate a plain-language summary of the critique's strengths and weaknesses.

    Returns:
        dict with keys 'strengths' (list of strings) and 'weaknesses' (list of strings).
    """
    strengths = []
    weaknesses = []

    for crit in CRITIC_CRITERIA:
        score = int(critique.get(crit, 0) or 0)
        label = CRITERION_LABELS[crit]
        descs = CRITERION_DESCRIPTIONS[crit]

        if score == 2:
            strengths.append(f"{label}: {descs['good']}")
        elif score == 1:
            weaknesses.append(f"{label}: {descs['weak']}")
        else:
            weaknesses.append(f"{label}: {descs['bad']}")

    # Also surface any specific issues the critic listed
    specific_issues = critique.get("issues", []) or []

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "specific_issues": specific_issues,
        "all_perfect": len(weaknesses) == 0,
    }


def critique_listing(raw_input: str, listing: dict, language: str = "english") -> dict:
    """Evaluate a generated listing against the original input."""
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

    # Recompute total in Python — LLM arithmetic is unreliable
    critique["total_score"] = _recompute_total(critique)
    critique["verdict"] = "PASS" if critique["total_score"] >= PASS_THRESHOLD else "FAIL"

    # Attach a human-readable summary
    critique["summary"] = summarize_critique(critique)

    return critique


def needs_refinement(critique: dict) -> bool:
    """Returns True if the total score is below the pass threshold."""
    return critique.get("total_score", 0) < PASS_THRESHOLD
