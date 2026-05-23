"""Validate the LLM response and compute the trust score deterministically."""

REQUIRED_FIELDS = {
    "title": str,
    "description": str,
    "category": str,
    "tags": list,
    "trust_signals": dict,
    "trust_explanation": str,
    "whatsapp_pitch": str,
}

TRUST_SIGNALS_SCHEMA = {
    "has_price": (bool, 15),
    "has_condition": (bool, 10),
    "has_accessories": (bool, 10),
    "has_brand_and_model": (bool, 10),
    "has_warranty": (bool, 5),
}

BASE_SCORE = 50


def compute_trust_score(signals: dict) -> int:
    """Deterministically compute the trust score from detected signals."""
    score = BASE_SCORE
    for signal, (_, weight) in TRUST_SIGNALS_SCHEMA.items():
        if signals.get(signal, False) is True:
            score += weight
    return min(score, 100)


def validate_listing(listing: dict) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in listing:
            return False, f"Missing required field: {field}"
        if not isinstance(listing[field], expected_type):
            return False, f"Field '{field}' should be {expected_type.__name__}"

    signals = listing["trust_signals"]
    for signal_name, (expected_type, _) in TRUST_SIGNALS_SCHEMA.items():
        if signal_name not in signals:
            return False, f"Missing trust signal: {signal_name}"
        if not isinstance(signals[signal_name], expected_type):
            return False, f"Trust signal '{signal_name}' must be a boolean"

    if len(listing["tags"]) < 1:
        return False, "tags must contain at least 1 item"

    return True, ""


def enrich_listing(listing: dict) -> dict:
    """Add the computed trust_score to a validated listing."""
    listing["trust_score"] = compute_trust_score(listing["trust_signals"])
    return listing
