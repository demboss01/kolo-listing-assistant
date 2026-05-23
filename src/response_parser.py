"""Validate the LLM response and compute the trust score deterministically."""
import re

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

SIGNAL_LABELS = {
    "has_price": "price",
    "has_condition": "condition",
    "has_accessories": "accessories",
    "has_brand_and_model": "brand and model",
    "has_warranty": "warranty or documents",
}

BASE_SCORE = 50

# Regex matches: any sequence of 3+ digits (with optional thousand separators
# or 'k' shorthand). Catches "150000", "150,000", "150 000", "150k", "300k",
# "5000 fcfa", "$200". Two+ digit numbers like "50" or "99" are too ambiguous
# to count as prices.
PRICE_PATTERN = re.compile(
    r"""
    \b              # word boundary
    (?:
        \d{1,3}     # 1-3 leading digits
        (?:[ ,]\d{3})+   # one or more groups of comma/space + 3 digits
        |
        \d{3,}      # OR 3+ consecutive digits
        |
        \d+\s?k     # OR digits followed by 'k' shorthand (e.g. 150k, 150 k)
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def input_contains_price(raw_input: str) -> bool:
    """Deterministic price detection from the raw input string.

    Returns True if the input contains any number that could be a price.
    Examples that match: '150000', '150,000', '150 000', '150k', '5000 fcfa',
    '$200', '300k fcfa'.
    Examples that don't: 'phone for sale', 'used moto', 'asdfghjkl'.
    """
    return bool(PRICE_PATTERN.search(raw_input))


def compute_trust_score(signals: dict) -> int:
    """Deterministically compute the trust score from detected signals."""
    score = BASE_SCORE
    for signal, (_, weight) in TRUST_SIGNALS_SCHEMA.items():
        if signals.get(signal, False) is True:
            score += weight
    return min(score, 100)


def generate_trust_explanation(signals: dict) -> str:
    """Produce a plain-language explanation from the trust signals dict."""
    present = [SIGNAL_LABELS[s] for s, val in signals.items() if val is True]
    missing = [SIGNAL_LABELS[s] for s, val in signals.items() if val is False]

    parts = []
    if present:
        parts.append(f"Includes: {', '.join(present)}.")
    if missing:
        parts.append(f"Missing: {', '.join(missing)}.")

    if not parts:
        return "No trust signals available."
    return " ".join(parts)


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


def enrich_listing(listing: dict, raw_input: str = "") -> dict:
    """Add computed trust_score and trust_explanation to a validated listing.

    Also overrides has_price with a deterministic Python regex check on the
    raw input, since the LLM's has_price judgment is inconsistent.
    """
    # Deterministically detect price in the raw input
    if raw_input:
        actual_has_price = input_contains_price(raw_input)
        listing["trust_signals"]["has_price"] = actual_has_price

    listing["trust_score"] = compute_trust_score(listing["trust_signals"])
    listing["trust_explanation"] = generate_trust_explanation(listing["trust_signals"])
    return listing