"""Plain English Python — paste code, get a beginner-friendly translation.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import hashlib
import os

import streamlit as st
from dotenv import load_dotenv

from explainer.llm import DEFAULT_MODEL, LLMError, explain_blocks, explain_overview
from explainer.parser import split_blocks
from explainer.samples import SAMPLES

load_dotenv()

st.set_page_config(
    page_title="Plain English Python",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 1500px;}
      .pep-card {
        border: 1px solid rgba(120,120,120,.25);
        border-radius: 12px;
        padding: 1rem 1.15rem;
        margin-bottom: .9rem;
        background: rgba(127,127,127,.05);
      }
      .pep-linetag {
        font-size: .74rem;
        letter-spacing: .06em;
        text-transform: uppercase;
        opacity: .6;
      }
      .pep-flow {
        border-left: 3px solid #7c93ff;
        padding: .1rem 0 .1rem .9rem;
        margin-bottom: 1rem;
      }
      .pep-empty {
        border: 1px dashed rgba(120,120,120,.4);
        border-radius: 12px;
        padding: 2.5rem 1.5rem;
        text-align: center;
        opacity: .7;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
for key, value in {
    "code": SAMPLES["Tip calculator (very short)"],
    "result": None,
    "error": None,
}.items():
    st.session_state.setdefault(key, value)


@st.cache_data(show_spinner=False, ttl=3600)
def run_explanation(code: str, audience: str, model: str, api_key: str) -> dict:
    """Cached so re-runs of the same code don't cost another API call."""
    blocks, syntax_error = split_blocks(code)
    overview = explain_overview(code, audience, model, api_key or None)
    explanations = explain_blocks(code, blocks, audience, model, api_key or None)
    return {
        "blocks": blocks,
        "syntax_error": syntax_error,
        "overview": overview,
        "explanations": explanations,
        "fingerprint": hashlib.sha256(code.encode()).hexdigest()[:8],
    }


def build_markdown(result: dict) -> str:
    overview = result["overview"]
    lines = [f"# {overview.get('headline', 'Code explanation')}", ""]
    lines += [overview.get("analogy", ""), ""]
    for bullet in overview.get("what_it_does", []):
        lines.append(f"- {bullet}")
    lines += ["", "## How it all connects", ""]
    for step in overview.get("connections", []):
        lines.append(f"**{step.get('step','')}** — {step.get('detail','')}")
        lines.append("")
    lines += ["## Line by line", ""]
    for block in result["blocks"]:
        item = result["explanations"].get(block.id, {})
        lines.append(f"### {block.line_label} — {item.get('title','')}")
        lines += ["", "```python", block.source, "```", "", item.get("explanation", "")]
        if item.get("connects_to"):
            lines += ["", f"*Connects to:* {item['connects_to']}"]
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    api_key = st.text_input(
        "Anthropic API key",
        value=env_key,
        type="password",
        help="Loaded from your .env file if present. Nothing is stored on disk.",
    )
    model = st.text_input("Model", value=DEFAULT_MODEL)
    audience = st.radio(
        "Explain it for",
        ["Absolute beginner", "Curious beginner"],
        help="Absolute beginner assumes zero programming vocabulary.",
    )

    st.divider()
    st.caption("Load a sample")
    sample_name = st.selectbox("Sample", list(SAMPLES), label_visibility="collapsed")
    if st.button("Load sample", use_container_width=True):
        st.session_state.code = SAMPLES[sample_name]
        st.session_state.result = None
        st.rerun()

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("📖 Plain English Python")
st.caption(
    "Paste Python code on the left. Get a jargon-free translation on the right — "
    "what it builds, what every line does, and how the pieces fit together."
)

left, right = st.columns([1, 1.25], gap="large")

# --------------------------------------------------------------------------
# Left: input
# --------------------------------------------------------------------------
with left:
    st.subheader("Your code")
    code = st.text_area(
        "Paste Python here",
        value=st.session_state.code,
        height=430,
        label_visibility="collapsed",
        placeholder="Paste any Python script here...",
    )
    st.session_state.code = code

    uploaded = st.file_uploader("...or upload a .py file", type=["py"])
    if uploaded is not None:
        st.session_state.code = uploaded.read().decode("utf-8", errors="replace")
        st.session_state.result = None
        st.rerun()

    go = st.button(
        "Explain this code", type="primary", use_container_width=True, disabled=not code.strip()
    )
    line_count = len(code.splitlines())
    st.caption(f"{line_count} lines")

if go:
    st.session_state.error = None
    with st.spinner("Reading the code and writing the explanation..."):
        try:
            st.session_state.result = run_explanation(code, audience, model, api_key)
        except LLMError as exc:
            st.session_state.result = None
            st.session_state.error = str(exc)

# --------------------------------------------------------------------------
# Right: output
# --------------------------------------------------------------------------
with right:
    st.subheader("Plain English")

    if st.session_state.error:
        st.error(st.session_state.error)

    result = st.session_state.result
    if result is None and not st.session_state.error:
        st.markdown(
            '<div class="pep-empty">Your translation will appear here.<br>'
            "Paste some code and press <b>Explain this code</b>.</div>",
            unsafe_allow_html=True,
        )

    if result:
        if result["syntax_error"]:
            st.warning(
                "This code has a syntax error, so it can't be split into clean steps: "
                f"{result['syntax_error']}"
            )

        overview_tab, lines_tab, flow_tab = st.tabs(
            ["Big picture", "Line by line", "How it connects"]
        )

        with overview_tab:
            overview = result["overview"]
            st.markdown(f"### {overview.get('headline', '')}")
            if overview.get("analogy"):
                st.info(overview["analogy"])
            if overview.get("what_it_does"):
                st.markdown("**What it actually does**")
                for bullet in overview["what_it_does"]:
                    st.markdown(f"- {bullet}")
            if overview.get("inputs_outputs"):
                st.markdown("**What goes in, what comes out**")
                st.markdown(overview["inputs_outputs"])
            if overview.get("key_terms"):
                with st.expander("Jargon buster"):
                    for term in overview["key_terms"]:
                        st.markdown(
                            f"**`{term.get('term','')}`** — {term.get('meaning','')}"
                        )

        with lines_tab:
            for block in result["blocks"]:
                item = result["explanations"].get(block.id, {})
                indent = "&nbsp;" * (4 * block.depth)
                st.markdown(
                    f'<div class="pep-linetag">{indent}{block.line_label} · {block.kind}</div>',
                    unsafe_allow_html=True,
                )
                st.code(block.source, language="python")
                st.markdown(f"**{item.get('title','')}**")
                st.markdown(item.get("explanation", ""))
                if item.get("connects_to"):
                    st.caption(f"↳ {item['connects_to']}")
                st.divider()

        with flow_tab:
            st.markdown(
                "Follow the information as it moves through the program, top to bottom."
            )
            for number, step in enumerate(result["overview"].get("connections", []), 1):
                st.markdown(
                    f'<div class="pep-flow"><b>{number}. {step.get("step","")}</b><br>'
                    f'{step.get("detail","")}</div>',
                    unsafe_allow_html=True,
                )

        st.download_button(
            "Download explanation (.md)",
            data=build_markdown(result),
            file_name=f"explanation-{result['fingerprint']}.md",
            mime="text/markdown",
            use_container_width=True,
        )
