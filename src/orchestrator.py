"""Orchestrator: runs the full generate → critique → refine pipeline."""
from src.llm_client import generate_listing
from src.response_parser import validate_listing, enrich_listing
from src.critic import critique_listing, needs_refinement, PASS_THRESHOLD
from src.refiner import refine_listing

MAX_REFINE_ATTEMPTS = 1


def optimize_listing(
    category: str,
    raw_input: str,
    language: str = "english",
) -> dict:
    """Generate, critique, and optionally refine a marketplace listing."""

    # Attempt 1: Generate
    try:
        initial = generate_listing(category, raw_input, language)
    except ValueError as e:
        return {"error": f"Generation failed: {e}", "attempts": 1}

    is_valid, validation_error = validate_listing(initial)
    if not is_valid:
        return {
            "error": f"Validation failed: {validation_error}",
            "listing": initial,
            "attempts": 1,
        }

    initial = enrich_listing(initial)

    # Critique attempt 1
    try:
        critique_1 = critique_listing(raw_input, initial, language)
    except ValueError as e:
        return {
            "listing": initial,
            "critique": None,
            "attempts": 1,
            "was_refined": False,
            "error": f"Critic failed: {e}",
        }

    # Decision: do we need to refine?
    if not needs_refinement(critique_1):
        return {
            "listing": initial,
            "critique": critique_1,
            "attempts": 1,
            "was_refined": False,
        }

    # Attempt 2: Refine
    try:
        refined = refine_listing(
            raw_input=raw_input,
            category=category,
            language=language,
            previous_listing=initial,
            critique=critique_1,
        )
    except ValueError:
        return {
            "listing": initial,
            "critique": critique_1,
            "attempts": 2,
            "was_refined": False,
        }

    is_valid, validation_error = validate_listing(refined)
    if not is_valid:
        return {
            "listing": initial,
            "critique": critique_1,
            "attempts": 2,
            "was_refined": False,
        }

    refined = enrich_listing(refined)

    # Critique attempt 2
    try:
        critique_2 = critique_listing(raw_input, refined, language)
    except ValueError:
        return {
            "listing": refined,
            "critique": None,
            "attempts": 2,
            "was_refined": True,
        }

    # Pick the higher-scoring attempt
    score_1 = critique_1.get("total_score", 0)
    score_2 = critique_2.get("total_score", 0)

    if score_2 > score_1:
        return {
            "listing": refined,
            "critique": critique_2,
            "attempts": 2,
            "was_refined": True,
        }
    else:
        return {
            "listing": initial,
            "critique": critique_1,
            "attempts": 2,
            "was_refined": False,
        }
