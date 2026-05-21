# 🔧 Implementation Guide — KOLO Listing Assistant

> Step-by-step build instructions for the CAP 942 capstone project, using **UV** as the Python package manager and **Ollama** for local LLM hosting on Apple Silicon.

---

## 📋 Table of Contents

1. [Why UV?](#-why-uv)
2. [Environment Setup](#-environment-setup-day-1)
3. [Project Initialization](#-project-initialization-day-1)
4. [Phase 1 — Core Pipeline (v1)](#-phase-1--core-pipeline-v1-days-3-4)
5. [Phase 2 — Streamlit UI](#-phase-2--streamlit-ui-days-5-7)
6. [Phase 3 — Vision Enhancement (v2, optional)](#-phase-3--vision-enhancement-v2-optional-days-8-9)
7. [Testing Strategy](#-testing-strategy)
8. [Deployment Checklist](#-deployment-checklist)
9. [Troubleshooting](#-troubleshooting)

---

## 🚀 Why UV?

**UV** is a Rust-based Python package and project manager from Astral (the makers of Ruff). For this project it offers three concrete advantages over `pip` + `venv`:

| Benefit | What it means for this project |
|---------|--------------------------------|
| **10–100× faster installs** | Streamlit + dependencies install in seconds, not minutes |
| **Built-in venv management** | One command (`uv sync`) replaces `python -m venv` + `pip install` |
| **Reproducible lockfiles** | `uv.lock` guarantees graders get the exact same dependency versions you used |
| **`pyproject.toml` native** | Modern Python project standard — looks professional in the repo |

> 💡 **Submission tip:** Mentioning UV in your presentation signals you're using current best practices.

---

## 🛠️ Environment Setup (Day 1)

### Step 1 — Install UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc
uv --version
```

### Step 2 — Install Ollama

Download from <https://ollama.com/download> or:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 3 — Pull the models

```bash
# Text model — required for v1 (~2.0 GB)
ollama pull llama3.2:3b

# Vision model — optional for v2 (~4.7 GB)
ollama pull llava:7b
```

> **Note:** Llama 3.2 3B is used instead of 3.1 8B because it runs ~2× faster on M1 Pro with only a minor quality tradeoff for structured JSON output.

### Step 4 — Verify Ollama is reachable

```bash
ollama list
curl http://localhost:11434/api/tags
```

If `curl` returns a connection error, run `ollama serve` in a separate terminal.

### Step 5 — Quick model smoke test

```bash
ollama run llama3.2:3b "Say hello in French in exactly five words."
```

---

## 📁 Project Initialization (Day 1)

### Step 1 — Clone and initialize

```bash
cd ~/Desktop
git clone https://github.com/demboss01/kolo-listing-assistant.git
cd kolo-listing-assistant
uv init --python 3.11
```

### Step 2 — Add dependencies

```bash
uv add streamlit ollama python-dotenv
uv add --dev pytest ruff
```

### Step 3 — Verify

```bash
uv run python -c "import streamlit, ollama; print('All good!')"
```

### Step 4 — Create folder structure

```bash
mkdir -p src prompts docs examples tests
touch src/__init__.py src/llm_client.py src/prompt_builder.py src/response_parser.py
touch prompts/listing_prompt.txt
touch examples/sample_inputs.json
touch tests/test_parser.py
touch .env.example
```

### Step 5 — First commit

```bash
git add .
git commit -m "Day 1: UV scaffold and folder structure"
git push origin main
```

✅ **Day 1 complete.**

---

## 🧠 Phase 1 — Core Pipeline (v1, Days 3–4)

### 1. The prompt template — `prompts/listing_prompt.txt`

This is the most important file in the project. Prompt quality determines output quality.

```text
You are an expert e-commerce listing optimizer for the KOLO marketplace,
which serves merchants in West Africa. Your job is to transform a rough,
informal product description into a polished, trust-optimized listing.

The merchant provided the following:
- Category: {category}
- Raw description: {raw_input}

Generate a structured listing. Respond with ONLY valid JSON in this exact
schema, no preamble, no markdown code fences:

{{
  "title": "string (8-14 words, search-optimized)",
  "description": "string (2-4 sentences covering condition, specs, accessories)",
  "category": "string (refined category if different from input)",
  "tags": ["array", "of", "5-7", "lowercase", "tags"],
  "trust_score": integer (0-100),
  "trust_explanation": "string (1-2 sentences on what trust signals are present/missing)",
  "whatsapp_pitch": "string (friendly 2-3 sentence message a seller can copy)"
}}

Rules:
- Write in the same language as the raw description (French or English).
- If the description is in French, respond in French.
- Trust score logic: start at 50, add points for:
  clear price (+15), condition stated (+10), accessories listed (+10),
  brand+model specific (+10), warranty/guarantee (+5).
- Be honest in trust_explanation about missing information.
- Never invent specifications not mentioned in the raw input.
- Tags must be lowercase, single words or hyphenated, no currency or price values.
```

### 2. The LLM client — `src/llm_client.py`

```python
"""Thin wrapper around the Ollama Python client."""
import json
import ollama
from pathlib import Path

MODEL_NAME = "llama3.2:3b"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "listing_prompt.txt"


def load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def generate_listing(category: str, raw_input: str) -> dict:
    """Send merchant input to the local LLM and return a parsed listing."""
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
```

### 3. The response parser — `src/response_parser.py`

```python
"""Validate that the LLM response matches the expected schema."""

REQUIRED_FIELDS = {
    "title": str,
    "description": str,
    "category": str,
    "tags": list,
    "trust_score": int,
    "trust_explanation": str,
    "whatsapp_pitch": str,
}


def validate_listing(listing: dict) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in listing:
            return False, f"Missing required field: {field}"
        if not isinstance(listing[field], expected_type):
            return False, f"Field '{field}' should be {expected_type.__name__}"

    score = listing["trust_score"]
    if not (0 <= score <= 100):
        return False, f"trust_score must be 0-100, got {score}"

    if len(listing["tags"]) < 3:
        return False, "tags must contain at least 3 items"

    return True, ""
```

### 4. Smoke test the pipeline

```bash
uv run python -c "
from src.llm_client import generate_listing
from src.response_parser import validate_listing

result = generate_listing(
    category='Phones & Tablets',
    raw_input='iphone 12 good condition 128gb black with charger 150000 fcfa'
)
is_valid, error = validate_listing(result)
print('Valid:', is_valid)
print('Result:', result)
"
```

If you get valid JSON back with all fields, **Phase 1 is done.**

---

## 🎨 Phase 2 — Streamlit UI (Days 5–7)

Create `app.py` at the project root:

```python
"""KOLO Listing Assistant — Streamlit entry point."""
import streamlit as st
from src.llm_client import generate_listing, warm_up
from src.response_parser import validate_listing

st.set_page_config(
    page_title="KOLO Listing Assistant",
    page_icon="🛍️",
    layout="wide"
)

# Warm up model on first load
if "warmed_up" not in st.session_state:
    with st.spinner("Loading model..."):
        warm_up()
    st.session_state.warmed_up = True

# Sidebar
with st.sidebar:
    st.title("🛍️ KOLO")
    st.caption("AI Listing Optimizer")
    category = st.selectbox(
        "Product Category",
        ["Phones & Tablets", "Electronics", "Vehicles", "Fashion",
         "Home & Garden", "Beauty", "Services", "Other"]
    )
    st.divider()
    st.markdown("**Try an example:**")
    examples = {
        "iPhone (EN)": "iphone 12 good condition 128gb black with charger 150000 fcfa",
        "iPhone (FR)": "iphone 12 bon état 128gb noir avec chargeur 150000 fcfa",
        "Motorcycle": "yamaha 125 2019 good engine 850000",
    }
    for label, text in examples.items():
        if st.button(label, use_container_width=True):
            st.session_state.input_text = text

# Main area
st.title("Transform rough listings into polished marketplace posts")
st.markdown("Type a brief product description below — informal language is fine.")

col_input, col_output = st.columns([1, 1.2])

with col_input:
    st.subheader("📝 Your Input")
    user_input = st.text_area(
        "Description",
        value=st.session_state.get("input_text", ""),
        height=200,
        placeholder="e.g., iphone 12 good condition 128gb..."
    )
    generate_button = st.button(
        "✨ Optimize Listing",
        type="primary",
        use_container_width=True,
        disabled=not user_input.strip()
    )

with col_output:
    st.subheader("✅ Optimized Output")

    if generate_button and user_input.strip():
        with st.spinner("Generating..."):
            try:
                listing = generate_listing(category, user_input)
                is_valid, error = validate_listing(listing)

                if not is_valid:
                    st.error(f"Validation failed: {error}")
                else:
                    st.markdown(f"### {listing['title']}")

                    score = listing["trust_score"]
                    color = "green" if score >= 70 else "orange" if score >= 40 else "red"
                    st.markdown(f"**Trust Score:** :{color}[{score} / 100]")
                    st.caption(listing["trust_explanation"])
                    st.progress(score / 100)

                    with st.expander("📄 Description", expanded=True):
                        st.write(listing["description"])

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Category:** {listing['category']}")
                    with col_b:
                        st.markdown(f"**Tags:** {', '.join(listing['tags'])}")

                    st.markdown("**💬 WhatsApp Pitch:**")
                    st.code(listing["whatsapp_pitch"], language=None)

            except Exception as e:
                st.error(f"Generation failed: {e}")
    else:
        st.info("👈 Enter a description and click **Optimize Listing**.")
```

Run it:

```bash
uv run streamlit run app.py
```

Test all three preset examples. UI polish checklist:

- [ ] Trust score color matches severity (green/orange/red)
- [ ] WhatsApp pitch shown in copyable code block
- [ ] Graceful error message if Ollama isn't running
- [ ] Loading spinner on every generation

✅ **End of Week 1: Submission-ready V1.**

---

## 📸 Phase 3 — Vision Enhancement (v2, optional, Days 8–9)

**Only proceed if Phase 2 is rock solid.**

Create `src/vision_extractor.py`:

```python
"""Extract visible product details from an uploaded photo using LLaVA."""
import base64
from io import BytesIO
import ollama
from PIL import Image

VISION_MODEL = "llava:7b"

VISION_PROMPT = """Look at this product photo and list ONLY visible facts:
- Product type (phone, laptop, motorcycle, etc.)
- Color
- Visible condition (scratches, cracks, wear)
- Visible accessories in the frame
- Any visible brand/model markings

Be brief. List facts only, no speculation. 3-5 short bullet points."""


def extract_visual_details(image_bytes: bytes) -> str:
    img = Image.open(BytesIO(image_bytes))
    img.thumbnail((800, 800))
    buffer = BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    response = ollama.chat(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": VISION_PROMPT,
            "images": [encoded]
        }]
    )
    return response["message"]["content"]
```

Wire it into `app.py` with a file uploader. If a photo is uploaded, call `extract_visual_details()` first and append the result to `user_input`. This is your **multi-step chain** for advanced rubric credit.

---

## 🧪 Testing Strategy

### `tests/test_parser.py`

```python
import pytest
from src.response_parser import validate_listing


def test_valid_listing_passes():
    listing = {
        "title": "iPhone 12 128GB",
        "description": "Excellent condition.",
        "category": "Phones",
        "tags": ["iphone", "apple", "smartphone"],
        "trust_score": 75,
        "trust_explanation": "Price and condition stated.",
        "whatsapp_pitch": "Hi! Selling my iPhone 12.",
    }
    is_valid, error = validate_listing(listing)
    assert is_valid


def test_missing_field_fails():
    listing = {"title": "Test"}
    is_valid, error = validate_listing(listing)
    assert not is_valid
    assert "Missing" in error


def test_out_of_range_score_fails():
    listing = {
        "title": "T", "description": "D", "category": "C",
        "tags": ["a", "b", "c"], "trust_score": 150,
        "trust_explanation": "E", "whatsapp_pitch": "P"
    }
    is_valid, error = validate_listing(listing)
    assert not is_valid
```

Run with `uv run pytest -v`.

### Manual demo test cases

1. ✅ Vague English input (`"phone for sale"`)
2. ✅ Detailed French input
3. ✅ Non-tech category (motorcycle)
4. ✅ Empty input (button disabled)
5. ✅ Very long input (300+ words)
6. ✅ Nonsense input (`"asdfghjkl"`)

---

## ✅ Deployment Checklist

- [ ] `README.md` reflects final feature set
- [ ] `uv.lock` is committed
- [ ] `docs/proposal.pdf` is in the repo
- [ ] `docs/workflow_diagram.png` is in the repo
- [ ] `docs/presentation.pdf` is in the repo
- [ ] All tests pass: `uv run pytest`
- [ ] App launches cleanly from a fresh clone:
  ```bash
  git clone https://github.com/demboss01/kolo-listing-assistant.git
  cd kolo-listing-assistant
  uv sync
  uv run streamlit run app.py
  ```
- [ ] Backup demo video recorded
- [ ] Final commit pushed to `main`

---

## 🔧 Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Connection refused` on first generation | Ollama not running | Run `ollama serve` in a separate terminal |
| `Model 'llama3.2:3b' not found` | Model not pulled | `ollama pull llama3.2:3b` |
| `Error: EOF` during model pull | Registry hiccup | Retry; if persistent, try `llama3.2:3b` or `moondream` |
| First generation takes 5+ seconds | Cold-start model load | Normal — subsequent calls are sub-second |
| Invalid JSON errors | Prompt drift | Verify `format="json"` is set in `llm_client.py` |
| Streamlit blank page | Browser cache | Hard refresh (Cmd+Shift+R) |
| `uv: command not found` | Shell PATH not refreshed | Restart terminal or `source ~/.zshrc` |
| Vision model OOM | LLaVA + text model loaded together | Use only one at a time |

---

## 📚 Reference Commands

```bash
# Daily workflow
uv sync                          # install/update all dependencies
uv run streamlit run app.py      # run the app
uv run pytest                    # run tests
uv add <package>                 # add a dependency

# Ollama
ollama list
ollama pull <model>
ollama serve

# Git
git add . && git commit -m "msg" && git push origin main
```

---

**Author:** Capstone Project — CAP 942
**Repository:** [demboss01/kolo-listing-assistant](https://github.com/demboss01/kolo-listing-assistant)
**Last Updated:** May 2026
