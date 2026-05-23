"""Programmatic fact-checker: strips hallucinated facts from LLM output.

Runs after the LLM has generated a listing. For each "specific fact" claim
in the output (price number, accessories, condition, brand/model), verifies
it appears in the raw input. If not, strips it from the listing.

This guarantees structurally that the output cannot contain facts absent
from the input — a guarantee the LLM cannot make on its own.
"""
import re

# ── Vocab the system recognizes ────────────────────────────────────────────

ACCESSORY_KEYWORDS = {
    "charger", "chargers", "chargeur", "chargeurs",
    "case", "etui", "étui",
    "box", "boite", "boîte",
    "earphones", "headphones", "écouteurs", "ecouteurs",
    "cable", "câble",
    "screen protector", "protection écran",
    "stand", "support",
    "remote",
}

CONDITION_KEYWORDS = {
    "good", "excellent", "new", "brand new", "brand-new", "used", "like new",
    "bon état", "bonne", "neuf", "neuve", "comme neuf", "occasion", "excellente",
}

# Brand families. If ANY of these brand words appear in the input,
# the listing is allowed to claim brand+model.
KNOWN_BRANDS = {
    "iphone", "apple", "samsung", "huawei", "xiaomi", "tecno", "infinix",
    "oppo", "vivo", "google", "pixel", "macbook", "ipad",
    "yamaha", "honda", "suzuki", "kawasaki", "toyota", "nissan", "peugeot",
    "renault", "mercedes", "bmw", "ford", "hyundai", "kia",
    "chanel", "dior", "gucci", "louis vuitton", "hermes", "prada",
    "nike", "adidas", "puma", "converse",
    "sony", "lg", "panasonic", "hp", "dell", "lenovo", "asus", "acer",
    "playstation", "ps5", "ps4", "xbox", "nintendo", "switch",
}


# ── Price normalization ────────────────────────────────────────────────────

PRICE_NUMBER_PATTERN = re.compile(
    r"""
    (?:
        \d{1,3}(?:[ ,]\d{3})+     # 150,000 or 150 000
        |
        \d+\s?k                   # 150k or 150 k
        |
        \d{3,}                    # 850000
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalize_price_token(token: str) -> int | None:
    """Convert '150k', '150,000', '150 000', '300000' to integer 150000 / 300000."""
    cleaned = token.lower().strip()
    cleaned = cleaned.replace(",", "").replace(" ", "")
    if cleaned.endswith("k"):
        try:
            return int(cleaned[:-1]) * 1000
        except ValueError:
            return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _extract_price_numbers(text: str) -> list[int]:
    """Return all price-shaped numbers in the text, normalized to integers."""
    matches = PRICE_NUMBER_PATTERN.findall(text)
    numbers = []
    for m in matches:
        n = _normalize_price_token(m)
        if n is not None and n >= 100:  # filter out tiny numbers that aren't prices
            numbers.append(n)
    return numbers


# ── Word presence checks ───────────────────────────────────────────────────

def _input_has_any_word(raw_input: str, vocab: set[str]) -> bool:
    """Returns True if any keyword from vocab appears as a word in raw_input."""
    text = raw_input.lower()
    for word in vocab:
        if word in text:
            return True
    return False


def _strip_phrases_from(text: str, phrases: list[str]) -> str:
    """Remove given phrases (case-insensitive) from text and clean up sentence fragments."""
    cleaned = text

    for phrase in phrases:
        # Try to remove entire sentence fragments that contain the phrase
        # Patterns that often surround hallucinated facts:
        patterns_to_strip = [
            # "It comes with a charger." / "It comes with chargers."
            rf"\bIt comes? (with|included? with)\s+\w*\s*{re.escape(phrase)}s?[.,]?",
            # "comes with charger"
            rf"\bcomes? with\s+\w*\s*{re.escape(phrase)}s?[.,]?",
            # "with charger" / "with the charger"
            rf"\bwith (the |a |an )?{re.escape(phrase)}s?[.,]?",
            # "avec chargeur" / "avec un chargeur"
            rf"\bavec (le |la |un |une )?{re.escape(phrase)}s?[.,]?",
            # "Includes a charger." / "Includes charger."
            rf"\b[Ii]ncludes? (a |the |an )?{re.escape(phrase)}s?[.,]?",
            # The phrase as standalone word
            rf"\b{re.escape(phrase)}s?\b",
        ]
        for pattern in patterns_to_strip:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Now clean up sentence fragments that lost their object:
    # "The price is ." → remove the whole sentence
    cleaned = re.sub(r"\bThe price is\s*[.,]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bPrice:\s*[.,]?\s*(?=[.,]|\s*$)", "", cleaned, flags=re.IGNORECASE)
    # "It comes with ." / "It comes ." → remove
    cleaned = re.sub(r"\bIt comes? (with|included)?\s*[.,]?\s*", "", cleaned, flags=re.IGNORECASE)
    # "comes included." / "that comes included" → remove
    cleaned = re.sub(r"\b(that |which )?comes? included[.,]?", "", cleaned, flags=re.IGNORECASE)
    # "priced at ." → remove
    cleaned = re.sub(r"\bpriced at\s*[.,]?\s*(?=[.,]|\s*$)", "", cleaned, flags=re.IGNORECASE)
    # "Le prix est de ." → remove
    cleaned = re.sub(r"\bLe prix est de\s*[.,]?\s*", "", cleaned, flags=re.IGNORECASE)

    # Tidy up double spaces, double commas, trailing punctuation chains
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*[,.]\s*[,.]+", ".", cleaned)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)
    cleaned = re.sub(r"^[\s,.]+", "", cleaned)  # strip leading punctuation
    cleaned = re.sub(r"\s*\.\s*$", ".", cleaned) if cleaned.endswith(".") else cleaned

    return cleaned.strip()


# ── Main fact-check function ───────────────────────────────────────────────

def fact_check_listing(listing: dict, raw_input: str) -> tuple[dict, list[str], list[str]]:
    """Strip hallucinated facts from a listing.

    Returns:
        (cleaned_listing, list_of_changes_made, list_of_forbidden_facts)
        - changes: human-readable descriptions for UI display
        - forbidden_facts: specific tokens the sanitizer must avoid
    """
    changes: list[str] = []
    forbidden: list[str] = []
    raw_lower = raw_input.lower()
    title = listing.get("title", "")
    description = listing.get("description", "")
    pitch = listing.get("whatsapp_pitch", "")
    signals = listing.get("trust_signals", {})

    # Check 1: Accessories
    input_has_accessories = _input_has_any_word(raw_input, ACCESSORY_KEYWORDS)
    if signals.get("has_accessories") and not input_has_accessories:
        leaked = [w for w in ACCESSORY_KEYWORDS if w in (description + " " + pitch + " " + title).lower()]
        if leaked:
            description = _strip_phrases_from(description, leaked)
            pitch = _strip_phrases_from(pitch, leaked)
            title = _strip_phrases_from(title, leaked)
            changes.append(f"Removed hallucinated accessories: {', '.join(leaked[:3])}")
            forbidden.extend(leaked)
        signals["has_accessories"] = False
    elif not signals.get("has_accessories") and input_has_accessories:
        signals["has_accessories"] = True

    # Check 2: Condition
    input_has_condition = _input_has_any_word(raw_input, CONDITION_KEYWORDS)
    if signals.get("has_condition") and not input_has_condition:
        leaked_conditions = []
        combined = (title + " " + description + " " + pitch).lower()
        for word in CONDITION_KEYWORDS:
            if re.search(rf"\b{re.escape(word)}\b", combined):
                leaked_conditions.append(word)
        if leaked_conditions:
            title = _strip_phrases_from(title, leaked_conditions)
            description = _strip_phrases_from(description, leaked_conditions)
            pitch = _strip_phrases_from(pitch, leaked_conditions)
            changes.append(f"Removed hallucinated condition: {', '.join(leaked_conditions[:2])}")
            forbidden.extend(leaked_conditions)
        signals["has_condition"] = False
    elif not signals.get("has_condition") and input_has_condition:
        signals["has_condition"] = True

    # Check 3: Price number consistency
    input_prices = _extract_price_numbers(raw_input)
    output_prices = _extract_price_numbers(description + " " + pitch)

    if not input_prices and output_prices:
        description = re.sub(PRICE_NUMBER_PATTERN, "", description)
        pitch = re.sub(PRICE_NUMBER_PATTERN, "", pitch)
        description = re.sub(r"\bPrice:\s*FCFA\.?", "", description, flags=re.IGNORECASE)
        description = re.sub(r"\bFCFA\.?\s*", "", description)
        pitch = re.sub(r"\bPrice:\s*FCFA\.?", "", pitch, flags=re.IGNORECASE)
        pitch = re.sub(r"\bFCFA\.?\s*", "", pitch)
        pitch = re.sub(r"\s+", " ", pitch).strip()
        description = re.sub(r"\s+", " ", description).strip()
        changes.append(f"Removed hallucinated price (input has no price)")
        forbidden.append("any price")  # tells sanitizer to omit price entirely
        signals["has_price"] = False

    elif input_prices and output_prices:
        if not any(p in input_prices for p in output_prices):
            correct_price = input_prices[0]
            formatted = f"{correct_price:,}"
            description = re.sub(PRICE_NUMBER_PATTERN, formatted, description, count=1)
            pitch = re.sub(PRICE_NUMBER_PATTERN, formatted, pitch, count=1)
            description = re.sub(PRICE_NUMBER_PATTERN, "", description)
            pitch = re.sub(PRICE_NUMBER_PATTERN, "", pitch)
            changes.append(f"Corrected price number to match input ({correct_price:,})")

    # Check 4: Brand presence
    if signals.get("has_brand_and_model"):
        input_has_brand = any(brand in raw_lower for brand in KNOWN_BRANDS)
        if not input_has_brand:
            signals["has_brand_and_model"] = False
            changes.append("Cleared has_brand_and_model (no recognized brand in input)")

    # Rebuild listing
    cleaned_listing = dict(listing)
    cleaned_listing["title"] = title.strip() or "For sale"
    cleaned_listing["description"] = description.strip() or "Listing available for sale. Contact seller for details."
    cleaned_listing["whatsapp_pitch"] = pitch.strip() or "Hello, contact me for details."
    cleaned_listing["trust_signals"] = signals

    return cleaned_listing, changes, forbidden