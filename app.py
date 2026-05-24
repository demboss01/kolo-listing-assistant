"""KOLO Listing Assistant — Streamlit web interface."""
import streamlit as st
from src.orchestrator import optimize_listing
from src.llm_client import warm_up

st.set_page_config(
    page_title="KOLO Listing Assistant",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "warmed_up" not in st.session_state:
    with st.spinner("Loading model into memory..."):
        try:
            warm_up()
            st.session_state.warmed_up = True
        except Exception as e:
            st.error(f"Could not connect to Ollama: {e}")
            st.info("Make sure Ollama is running: `ollama serve` in another terminal.")
            st.stop()

with st.sidebar:
    st.image("docs/images/logos/kolo-icon.png", use_container_width=True)
    st.markdown("### Listing Assistant")
    st.caption("AI tool for KOLO.ci merchants — runs 100% locally")
    st.divider()

    language = st.radio(
        "Output Language",
        options=["english", "french"],
        format_func=lambda x: "🇬🇧 English" if x == "english" else "🇨🇮 Français",
        horizontal=True,
    )

    category = st.selectbox(
        "Product Category",
        ["Phones & Tablets", "Electronics", "Vehicles", "Fashion",
         "Home & Garden", "Beauty", "Services", "Other"]
    )

    st.divider()
    st.markdown("**Quick Examples**")

    examples = {
        "📱 iPhone (EN)": ("Phones & Tablets", "english", "iphone 12 good condition 128gb black with charger 150000 fcfa"),
        "📱 iPhone (FR)": ("Phones & Tablets", "french", "iphone 12 bon état 128gb noir avec chargeur 150000 fcfa"),
        "🏍️ Yamaha (FR)": ("Vehicles", "french", "yamaha 125 2019 papiers à jour 850000"),
        "💄 Perfume (FR)": ("Beauty", "french", "parfum chanel coco mademoiselle 100ml authentique 45000"),
        "🧪 Vague": ("Phones & Tablets", "english", "phone 50000"),
    }

    for label, (cat, lang, text) in examples.items():
        if st.button(label, use_container_width=True):
            st.session_state.input_text = text
            st.session_state.preset_category = cat
            st.session_state.preset_language = lang

    st.divider()
    st.caption("Built with Llama 3.2 via Ollama — runs 100% locally.")
    st.caption("[GitHub](https://github.com/demboss01/kolo-listing-assistant)")

if "preset_language" in st.session_state:
    language = st.session_state.preset_language
    del st.session_state.preset_language
if "preset_category" in st.session_state:
    category = st.session_state.preset_category
    del st.session_state.preset_category

st.title("Transform rough listings into polished marketplace posts")
st.markdown(
    "Type a brief product description. The AI will generate a structured "
    "listing, critique its own output, and refine it if needed."
)

col_input, col_output = st.columns([1, 1.3])

with col_input:
    st.subheader("📝 Your Input")
    user_input = st.text_area(
        "Description",
        value=st.session_state.get("input_text", ""),
        height=180,
        placeholder=(
            "e.g., iphone 12 bon état 128gb noir avec chargeur 150000 fcfa\n"
            "      yamaha 125 2019 papiers à jour 850000\n"
            "      parfum chanel coco mademoiselle 100ml"
        ),
        key="input_text",
    )

    generate_button = st.button(
        "✨ Optimize Listing",
        type="primary",
        use_container_width=True,
        disabled=not user_input.strip(),
    )

with col_output:
    st.subheader("✅ Optimized Output")

    if generate_button and user_input.strip():
        with st.spinner("AI is generating, critiquing, and refining..."):
            try:
                result = optimize_listing(
                    category=category,
                    raw_input=user_input,
                    language=language,
                )
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                st.stop()

        if "error" in result and "listing" not in result:
            st.error(f"❌ {result['error']}")
            st.stop()

        listing = result["listing"]
        critique = result.get("critique")
        attempts = result.get("attempts", 1)
        was_refined = result.get("was_refined", False)

        if was_refined:
            st.success(f"✨ Refined after {attempts} attempts")
        elif attempts > 1:
            st.info(f"ℹ️ Attempted refinement, original was kept ({attempts} attempts)")
        else:
            st.success("✅ First-attempt success")

        st.markdown("### Title")
        st.code(listing["title"], language=None)

        score = listing.get("trust_score", 0)
        color = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
        st.markdown(
            f"**🛡️ Buyer Trust Score:** {color} {score} / 100  "
            f"*(based on how much info the merchant provided)*"
        )
        st.progress(score / 100)
        st.caption(listing.get("trust_explanation", ""))

        with st.expander("📄 Description", expanded=True):
            st.write(listing["description"])

        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.markdown(f"**Category:** {listing['category']}")
        with col_b:
            tags_display = " · ".join(f"`{t}`" for t in listing["tags"])
            st.markdown(f"**Tags:** {tags_display}")

        st.markdown("### 💬 WhatsApp Pitch")
        st.code(listing["whatsapp_pitch"], language=None)
        st.caption("👆 Click the copy icon in the top-right to copy to clipboard")

        with st.expander("🤖 AI Process — How the multi-step chain worked", expanded=True):
            st.info(
                "**Two scores, two different questions:**  \n"
                "🛡️ **Buyer Trust Score** measures how much info the merchant gave "
                "(a sparse input scores low even if the AI does its job perfectly).  \n"
                "✍️ **AI Quality Score** below measures how well the AI wrote the "
                "listing from whatever info it had."
            )

            # ─── NEW: Pipeline trace ───────────────────────────────
            trace = result.get("trace", [])
            if trace:
                st.markdown("### 🛠️ Pipeline Steps")
                for i, step in enumerate(trace, 1):
                    name = step["name"]
                    status = step["status"]
                    detail = step["detail"]
                    duration = step["duration"]

                    # Pick an icon and color based on status
                    icon_map = {
                        "done": "✅", "clean": "✅",
                        "caught": "🛡️", "skipped": "⏭️", "error": "❌",
                    }
                    icon = icon_map.get(status, "•")

                    dur_str = f" ({duration}s)" if duration > 0 else ""
                    st.markdown(f"**{icon} Step {i} — {name}**  *{status.upper()}{dur_str}*")
                    if detail:
                        st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;{detail}", unsafe_allow_html=True)

                st.divider()

            # ─── Existing summary content below ────────────────────
            st.markdown(f"**LLM calls made:** {attempts * 2 if attempts > 1 else 2}")
            st.markdown(f"**Refinement triggered:** {'Yes' if attempts > 1 else 'No'}")
            st.markdown(f"**Refinement accepted:** {'Yes' if was_refined else 'No'}")

            if critique:
                st.divider()
                summary = critique.get("summary", {})
                strengths = summary.get("strengths", [])
                weaknesses = summary.get("weaknesses", [])
                specific_issues = summary.get("specific_issues", [])

                if summary.get("all_perfect"):
                    st.success("✓ **All criteria scored full marks — no issues found.**")
                else:
                    if strengths:
                        st.markdown("**✓ What's good:**")
                        for s in strengths[:3]:
                            st.markdown(f"- {s}")
                        if len(strengths) > 3:
                            st.caption(f"_…plus {len(strengths) - 3} more strong areas_")
                    if weaknesses:
                        st.markdown("**⚠ What could improve:**")
                        for w in weaknesses:
                            st.markdown(f"- {w}")
                    if specific_issues:
                        st.markdown("**🔍 Critic's specific notes:**")
                        for issue in specific_issues:
                            st.markdown(f"- {issue}")

                st.divider()
                st.markdown("**✍️ AI Quality Score (out of 12):**")
                criteria = [
                    ("Faithfulness", critique.get("faithfulness", 0)),
                    ("Completeness", critique.get("completeness", 0)),
                    ("Language consistency", critique.get("language_consistency", 0)),
                    ("Format quality", critique.get("format_quality", 0)),
                    ("Tone appropriateness", critique.get("tone_appropriateness", 0)),
                    ("Title quality", critique.get("title_quality", 0)),
                ]
                for name, val in criteria:
                    bar = "█" * val + "░" * (2 - val)
                    st.text(f"{name:24} {bar}  {val}/2")
                st.markdown(f"**Total:** {critique.get('total_score', 0)} / 12 — **{critique.get('verdict', 'N/A')}**")

    else:
        st.info("👈 Type a product description and click **Optimize Listing**.")