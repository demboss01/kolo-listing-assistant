# 🛍️ KOLO Listing Assistant

> An offline AI tool that transforms rough, informal merchant inputs into polished, trust-optimized marketplace listings — running entirely on a local LLM, with no paid APIs and no internet required at runtime.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![UV](https://img.shields.io/badge/Package%20Manager-UV-7C3AED)
![Streamlit](https://img.shields.io/badge/Streamlit-1.57-FF4B4B)
![Ollama](https://img.shields.io/badge/Ollama-Llama%203.2%203B-black)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Day%201%20Complete%20%E2%80%94%20Scaffold%20Ready-success)

---

## 📖 Overview

The **KOLO Listing Assistant** is a capstone project built for **CAP 942 — Capstone Project: AI Application Development**. It solves a concrete problem faced by informal-market merchants in West Africa: rough, unstructured marketplace listings that lose buyers and reduce trust scores.

A merchant types a brief, casual description — for example, *"iphone 12 good condition 128gb black with charger 150000 fcfa"* — and the application returns a structured, polished listing with a title, description, suggested category, tags, a trust-quality score, and a ready-to-send WhatsApp pitch. Everything runs locally on the user's machine through [Ollama](https://ollama.com), with no data ever leaving the device.

---

## ✨ Features

- 🎯 **Single-input simplicity** — paste a rough description, get a polished listing in seconds
- 🏷️ **Auto-generated title** — search-optimized, 8–14 words
- 📝 **Structured description** — condition, specs, accessories, guarantees
- 🗂️ **Smart categorization** — suggested category and tags
- 🛡️ **Trust-quality score** — 0–100 score with explanation of missing trust signals
- 💬 **WhatsApp pitch** — copy-paste-ready conversational message for buyers
- 🔒 **Fully offline** — no API keys, no paid services, no data leaves your machine
- 📸 **Photo support** *(v2, optional)* — upload a product image for vision-augmented generation

---

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌────────────────┐
│  Streamlit UI   │ ───▶ │ Prompt Assembler │ ───▶ │  Ollama Local  │
│  (User Input)   │      │   (Templating)   │      │  Llama 3.2 3B  │
└─────────────────┘      └──────────────────┘      └────────┬───────┘
        ▲                                                    │
        │                                                    ▼
        │                ┌──────────────────┐      ┌────────────────┐
        └──────────────  │ JSON Parser +    │ ◀─── │ Structured     │
                         │  Validator       │      │ JSON Response  │
                         └──────────────────┘      └────────────────┘
```

A more detailed workflow diagram lives in [`docs/workflow_diagram.png`](docs/workflow_diagram.png).

---

## 🛠️ Tech Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| Language | Python 3.11 | Application logic |
| Package Manager | [UV](https://docs.astral.sh/uv/) | Fast, reproducible Python project management |
| LLM Runtime | [Ollama](https://ollama.com) | Local model hosting |
| Text Model | Llama 3.2 3B | Listing generation |
| Vision Model *(v2)* | LLaVA 7B | Photo-based extraction |
| UI Framework | [Streamlit](https://streamlit.io) | Web interface |
| Image Handling | Pillow | Image preprocessing (v2) |

---

## 📦 Installation

### Prerequisites

- **macOS, Linux, or Windows** with at least **16 GB RAM**
- **Python 3.11+** (UV will install this for you if missing)
- **Ollama** ([download](https://ollama.com/download))
- **~7 GB free disk space** for model weights

> **Tested on:** Apple M1 Pro, 16 GB RAM, macOS. Performance: ~1–3 seconds per generation.

### Step 1 — Install UV

UV is a fast, modern Python package manager that handles virtual environments and dependencies in one tool.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify
uv --version
```

### Step 2 — Install Ollama and pull the model

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Pull the text model (~2.0 GB)
ollama pull llama3.2:3b

# Optional: pull the vision model for v2 photo support (~4.7 GB)
ollama pull llava:7b
```

Verify Ollama is running:

```bash
ollama list
```

### Step 3 — Clone the repository

```bash
git clone https://github.com/demboss01/kolo-listing-assistant.git
cd kolo-listing-assistant
```

### Step 4 — Sync dependencies

UV reads `pyproject.toml` and `uv.lock` to install everything in a managed virtual environment automatically:

```bash
uv sync
```

That single command replaces `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`. Everything is installed in `.venv/` and locked to the exact versions in `uv.lock`.

### Step 5 — Run the application

```bash
uv run streamlit run app.py
```

The app will open automatically at `http://localhost:8501`.

---

## 🚀 Usage

1. **Select a product category** from the dropdown in the sidebar.
2. **Paste your rough listing** into the text area — informal language is fine, French or English are both supported.
3. **(Optional, v2)** Upload a product photo.
4. **Click "Optimize Listing"** and wait a few seconds.
5. **Review the structured output** on the right: title, description, tags, trust score, and WhatsApp pitch.
6. **Copy any field** to your clipboard with the per-field copy button.

### Example

**Input:**
```
iphone 12 good condition 128gb black with charger 150000 fcfa
```

**Output:**
```
Title:        iPhone 12 128GB Black — Excellent Condition with Original Charger
Category:     Phones & Tablets
Tags:         iphone, apple, smartphone, 128gb, black
Trust Score:  78 / 100
Pitch:        Hello! I'm selling my iPhone 12 (128GB, black) in
              excellent condition with its original charger. Price: 150,000 FCFA.
              Available for demonstration. Interested?
```

---

## 📁 Project Structure

```
kolo-listing-assistant/
├── app.py                      # Streamlit entry point
├── pyproject.toml              # UV project manifest
├── uv.lock                     # Locked dependency versions
├── .python-version             # Python 3.11 pinned
├── README.md                   # This file
├── IMPLEMENTATION.md           # Step-by-step build guide
├── LICENSE                     # MIT License
├── .gitignore
├── .env.example                # Configuration template
│
├── src/
│   ├── __init__.py
│   ├── llm_client.py           # Ollama HTTP client wrapper
│   ├── prompt_builder.py       # Prompt assembly logic
│   ├── response_parser.py      # JSON validation and parsing
│   └── vision_extractor.py     # (v2) Photo description pipeline
│
├── prompts/
│   ├── listing_prompt.txt      # Main generation template
│   └── vision_prompt.txt       # (v2) Vision extraction template
│
├── docs/
│   ├── proposal.pdf            # CAP 942 project proposal
│   ├── workflow_diagram.png    # Architecture diagram
│   └── presentation.pdf        # Final presentation slides
│
├── examples/
│   ├── sample_inputs.json      # Test cases for demos
│   └── sample_outputs.json     # Expected outputs
│
└── tests/
    └── test_parser.py          # Output validation tests
```

---

## 🎓 Academic Context

This project was developed for **CAP 942 — Capstone Project: AI Application Development**. It satisfies all course requirements:

- ✅ Uses an open-source LLM (Llama 3.2 via Ollama)
- ✅ Accepts user input and produces LLM-generated output
- ✅ Runs as a Streamlit web application
- ✅ Implements an optional multi-step chain (vision → text) for advanced rubric credit
- ✅ Operates entirely without paid APIs

For the full problem statement, methodology, and design rationale, see [`docs/proposal.pdf`](docs/proposal.pdf).

---

## 🗺️ Roadmap

- [x] Project proposal submitted
- [x] Repository scaffolded with UV
- [ ] Core prompt template developed
- [ ] LLM client and response parser implemented
- [ ] Streamlit UI complete (v1)
- [ ] End-to-end testing with realistic merchant inputs
- [ ] Vision model integration (v2, optional)
- [ ] Workflow diagram and final documentation
- [ ] Presentation deck and backup demo video
- [ ] Final submission to Canvas

---

## ⚠️ Known Limitations

- **Cold-start latency** — the first generation after launching the app takes ~3–5 seconds while the model loads into memory. Subsequent generations are fast (~1–3 seconds).
- **Output variability** — LLM responses are non-deterministic by nature. The same input may produce slightly different outputs across runs.
- **Vision model accuracy *(v2)*** — vision models occasionally misidentify product details, especially in low-light photos. The text model still produces a usable listing from the merchant's typed input.
- **Hardware dependency** — performance is best on Apple Silicon or recent Intel/AMD machines with 16 GB+ RAM. On lower-end hardware, consider using `moondream` as an even lighter alternative.

---

## 🤝 Contributing

This is a graded academic project and is not currently accepting external contributions. Once the course has concluded, contributions and forks are welcome.

---

## 📜 License

This project is released under the [MIT License](LICENSE). You are free to use, modify, and distribute it with attribution.

---

## 🙏 Acknowledgments

- The CAP 942 instructional team for the capstone framework
- [Astral](https://astral.sh) for [UV](https://docs.astral.sh/uv/), the package manager used in this project
- [Ollama](https://ollama.com) for making local LLM hosting effortless
- [Meta AI](https://ai.meta.com) for releasing Llama 3.2 under an open license
- The KOLO marketplace project, which inspired the problem framing

---

## 📬 Contact

**Author:** Mamadou Dembele
**Course:** CAP 942 — Capstone Project: AI Application Development
**GitHub:** [@demboss01](https://github.com/demboss01)
**Repository:** [demboss01/kolo-listing-assistant](https://github.com/demboss01/kolo-listing-assistant)

For questions about the project, open an [issue](https://github.com/demboss01/kolo-listing-assistant/issues) on this repository.
