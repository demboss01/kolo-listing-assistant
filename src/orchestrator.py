"""Orchestrator: full generate → fact-check → critique → refine pipeline."""
import time
from src.llm_client import generate_listing
from src.response_parser import validate_listing, enrich_listing
from src.critic import critique_listing, needs_refinement, PASS_THRESHOLD
from src.refiner import refine_listing
from src.fact_checker import fact_check_listing


def _step(name: str, status: str, detail: str = "", duration: float = 0.0) -> dict:
    """Build a uniform pipeline step record for the UI trace."""
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "duration": round(duration, 2),
    }


def optimize_listing(category: str, raw_input: str, language: str = "english") -> dict:
    """Generate, fact-check, critique, and optionally refine a marketplace listing.

    Pipeline:
      1. Generate (LLM #1)
      2. Validate JSON schema (Python)
      3. Enrich with trust score (Python)
      4. Fact-Check Gate (Python — strips hallucinated facts)
      5. Critique (LLM #2)
      6. If score < threshold: Refine (LLM #3) → Re-fact-check → Re-critique (LLM #4)
      7. Best-of-attempts selection
    """
    trace: list[dict] = []

    # Step 1 — Generate
    t0 = time.time()
    try:
        initial = generate_listing(category, raw_input, language)
        trace.append(_step("Generate", "done",
                          "LLM created initial listing draft",
                          time.time() - t0))
    except ValueError as e:
        trace.append(_step("Generate", "error", str(e), time.time() - t0))
        return {"error": f"Generation failed: {e}", "attempts": 1, "trace": trace}

    # Step 2 — Validate
    t0 = time.time()
    is_valid, validation_error = validate_listing(initial)
    if not is_valid:
        trace.append(_step("Validate", "error", validation_error, time.time() - t0))
        return {"error": f"Validation failed: {validation_error}",
                "listing": initial, "attempts": 1, "trace": trace}
    trace.append(_step("Validate", "done",
                      "Confirmed JSON schema is well-formed", time.time() - t0))

    # Step 3 — Enrich
    t0 = time.time()
    initial = enrich_listing(initial, raw_input)
    trace.append(_step("Enrich", "done",
                      f"Computed trust score: {initial.get('trust_score', 0)}/100",
                      time.time() - t0))

    # Step 4 — Fact-Check Gate
    t0 = time.time()
    initial, fact_changes_1, _ = fact_check_listing(initial, raw_input)
    initial = enrich_listing(initial, raw_input)
    if fact_changes_1:
        trace.append(_step("Fact-Check Gate", "caught",
                          " | ".join(fact_changes_1), time.time() - t0))
    else:
        trace.append(_step("Fact-Check Gate", "clean",
                          "No hallucinations detected", time.time() - t0))

    # Step 5 — Critique attempt 1
    t0 = time.time()
    try:
        critique_1 = critique_listing(raw_input, initial, language)
        trace.append(_step("Critique", "done",
                          f"Score: {critique_1.get('total_score', 0)}/12",
                          time.time() - t0))
    except ValueError as e:
        trace.append(_step("Critique", "error", str(e), time.time() - t0))
        return {"listing": initial, "critique": None, "attempts": 1,
                "was_refined": False, "fact_check_changes": fact_changes_1,
                "trace": trace, "error": f"Critic failed: {e}"}

    # Decision: refine?
    if not needs_refinement(critique_1):
        trace.append(_step("Refine", "skipped",
                          f"Score {critique_1.get('total_score', 0)}/12 is above threshold {PASS_THRESHOLD}",
                          0))
        trace.append(_step("Finalize", "done", "Initial attempt accepted", 0))
        return {"listing": initial, "critique": critique_1, "attempts": 1,
                "was_refined": False, "fact_check_changes": fact_changes_1,
                "trace": trace}

    # Step 6 — Refine
    t0 = time.time()
    try:
        refined = refine_listing(raw_input=raw_input, category=category,
                                language=language, previous_listing=initial,
                                critique=critique_1)
        trace.append(_step("Refine", "done",
                          "LLM re-generated using critic's feedback",
                          time.time() - t0))
    except ValueError as e:
        trace.append(_step("Refine", "error", str(e), time.time() - t0))
        return {"listing": initial, "critique": critique_1, "attempts": 2,
                "was_refined": False, "fact_check_changes": fact_changes_1,
                "trace": trace}

    is_valid, _ = validate_listing(refined)
    if not is_valid:
        trace.append(_step("Validate (refined)", "error",
                          "Refined output had invalid JSON", 0))
        return {"listing": initial, "critique": critique_1, "attempts": 2,
                "was_refined": False, "fact_check_changes": fact_changes_1,
                "trace": trace}

    # Step 7 — Re-enrich + Re-fact-check
    refined = enrich_listing(refined, raw_input)
    t0 = time.time()
    refined, fact_changes_2, _ = fact_check_listing(refined, raw_input)
    refined = enrich_listing(refined, raw_input)
    if fact_changes_2:
        trace.append(_step("Fact-Check (refined)", "caught",
                          " | ".join(fact_changes_2), time.time() - t0))
    else:
        trace.append(_step("Fact-Check (refined)", "clean",
                          "No hallucinations detected", time.time() - t0))

    # Step 8 — Critique attempt 2
    t0 = time.time()
    try:
        critique_2 = critique_listing(raw_input, refined, language)
        trace.append(_step("Critique (refined)", "done",
                          f"Score: {critique_2.get('total_score', 0)}/12",
                          time.time() - t0))
    except ValueError as e:
        return {"listing": refined, "critique": None, "attempts": 2,
                "was_refined": True,
                "fact_check_changes": fact_changes_1 + fact_changes_2,
                "trace": trace, "error": str(e)}

    # Step 9 — Best-of-attempts
    score_1 = critique_1.get("total_score", 0)
    score_2 = critique_2.get("total_score", 0)
    if score_2 > score_1:
        trace.append(_step("Finalize", "done",
                          f"Refined version selected ({score_2}/12 > {score_1}/12)", 0))
        return {"listing": refined, "critique": critique_2, "attempts": 2,
                "was_refined": True,
                "fact_check_changes": fact_changes_1 + fact_changes_2,
                "trace": trace}
    else:
        trace.append(_step("Finalize", "done",
                          f"Initial kept ({score_1}/12 ≥ {score_2}/12)", 0))
        return {"listing": initial, "critique": critique_1, "attempts": 2,
                "was_refined": False,
                "fact_check_changes": fact_changes_1,
                "trace": trace}