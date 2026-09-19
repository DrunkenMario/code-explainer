# 📖 Plain English Python

Paste Python code, get a translation for someone who has never programmed: what the
whole script builds, what every line does, and how the pieces connect.

---

## Why Streamlit (not React)

You asked for the most rapid, lightweight option for a prototype. Streamlit wins here:

| | Streamlit | React + FastAPI |
|---|---|---|
| Processes to run | 1 | 2 (Vite dev server + API) |
| Language boundary | none — parsing, prompting and UI are all Python | JS/Python split, CORS, API contract |
| Code to write | ~500 lines | ~1,200 lines |
| Syntax-highlighted code display | built in (`st.code`) | add a highlighter library |

The parsing and prompting logic lives in `explainer/` with zero Streamlit imports, so
if this outgrows the prototype you can wrap that package in FastAPI and put React on
top without rewriting the core.

---

## Directory structure

```
code-explainer/
├── app.py                  # Streamlit UI (the whole frontend)
├── explainer/
│   ├── __init__.py
│   ├── parser.py           # AST splitter: code -> logical blocks with exact line numbers
│   ├── prompts.py          # Prompt templates (tune this file first)
│   ├── llm.py              # Anthropic API calls, JSON parsing, batching
│   └── samples.py          # Demo scripts for first-run
├── .streamlit/
│   └── config.toml         # Theme
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup

**1. Get the files and create a virtual environment**

```bash
cd code-explainer
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Add your API key**

```bash
cp .env.example .env
```

Open `.env` and paste your key from https://console.anthropic.com. You can also skip
this and paste the key into the app sidebar at runtime.

**4. Run it**

```bash
streamlit run app.py
```

It opens at http://localhost:8501. Click **Load sample** in the sidebar, then
**Explain this code**.

---

## How it works

The naive version of this app dumps the whole file into an LLM and asks for a
line-by-line explanation. That drifts: line numbers come out wrong, lines get merged,
and occasionally the model explains code that isn't there.

This version splits the work:

1. **`parser.py` cuts the code first.** Python's own `ast` module walks the file and
   produces exact blocks: one per statement, with headers (`def foo():`) separated from
   bodies when a construct is long, and clause lines (`else:`, `except ValueError:`)
   kept as their own steps. Line numbers come from the Python compiler, not the model,
   so they're always right. Comments are glued to the statement they document.
2. **The model explains blocks by ID.** Each block is handed over tagged
   `<block id="7" lines="12-14">`, and the model must return one JSON entry per ID.
   The full file is included as context in every call so explanations stay aware of the
   surrounding program.
3. **Two separate calls.** One for the big picture and connection map (whole-file view),
   one for the per-block detail (batched 10 blocks at a time so long files don't hit the
   output token ceiling).

Other details worth knowing:

- **Caching.** `@st.cache_data` keys on (code, audience, model), so re-running the same
  paste is free and instant.
- **Broken code still works.** A syntax error falls back to a single block plus a
  visible warning, instead of a stack trace.
- **Big files degrade gracefully.** Past 60 blocks, adjacent simple statements are merged
  so a 500-line script doesn't become 500 API calls.
- **JSON is forced** by prefilling `{` as the start of the assistant turn, then parsed
  defensively (fence stripping, truncation recovery).

---

## Cost and latency

Roughly, per explanation of a 50-line script with `claude-sonnet-5`:

- 1 overview call + 2 block calls ≈ 3 requests
- ~15–25k input tokens total (the file is resent as context per batch), ~4k output
- A few cents, 10–20 seconds

To cut this: raise `BATCH_SIZE` in `explainer/llm.py`, or switch the model to
`claude-haiku-4-5-20251001` in the sidebar for a cheaper, faster pass.

---

## Swapping in OpenAI

Only `explainer/llm.py` knows about Anthropic. Replace `_json_call` with an OpenAI
`chat.completions.create` using `response_format={"type": "json_object"}` and drop the
`{` prefill — nothing else changes.

---

## Sensible next steps

- Hover-to-highlight: clicking an explanation scrolls to and highlights the source lines
  (needs a custom component or a switch to React).
- "Explain this differently" button per block, for when one explanation doesn't land.
- Detect undefined names and imports of third-party libraries, and explain what the
  library is for before explaining the line that uses it.
- Streaming the overview so the first words appear in ~2 seconds instead of ~8.
