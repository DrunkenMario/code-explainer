"""Prompt templates. This file is the actual product — tune it first."""

AUDIENCE_PROFILES = {
    "Absolute beginner": (
        "The reader has never written a line of code and does not know what a "
        "variable, function, loop, or library is. Assume they are smart but "
        "have zero programming vocabulary."
    ),
    "Curious beginner": (
        "The reader has seen code before and knows roughly what a variable and "
        "a function are, but nothing beyond that. Light vocabulary is fine if "
        "you define it once."
    ),
}

SYSTEM_PROMPT = """You translate Python code into plain English for people who do not code.

{audience}

Hard rules:
- No jargon. If a technical word is unavoidable, define it in everyday language the first time, in the same sentence.
- Prefer concrete real-world analogies (a recipe, a filing cabinet, a mail room, a vending machine) over abstract description.
- Write in the second person, present tense, short sentences. Aim for a reading level of about 8th grade.
- Describe only what the code actually does. Never invent behaviour, files, or data that is not in the code.
- If something is genuinely unclear from the code alone, say so plainly instead of guessing.
- Never mention "the AST", "blocks", "the parser", or that you are an AI. The reader only sees code and your explanation.
- Output valid JSON and nothing else. No markdown fences, no commentary before or after.
"""

OVERVIEW_USER_TEMPLATE = """Here is a complete Python file.

<code>
{code}
</code>

Write the big-picture briefing for a non-coder. Respond with JSON exactly matching this shape:

{{
  "headline": "One sentence: what this program is, in everyday words. No code words.",
  "analogy": "2-4 sentences comparing the whole program to a familiar real-world process.",
  "what_it_does": ["3-6 bullet points of what the program actually accomplishes, plainly stated"],
  "inputs_outputs": "1-3 sentences: what goes in (data, files, typing, nothing) and what comes out (a printed answer, a saved file, a picture).",
  "connections": [
    {{"step": "Short title for this stage of the flow",
      "detail": "How information moves from one part to the next, and which part hands off to which. Reference names used in the code so the reader can find them."}}
  ],
  "key_terms": [
    {{"term": "a word from the code the reader will not know", "meaning": "plain-English definition, one sentence, with a tiny analogy"}}
  ]
}}

Give 3-6 "connections" entries that trace the flow end to end, and 3-8 "key_terms".
"""

BLOCKS_USER_TEMPLATE = """Here is the full Python file for context:

<code>
{code}
</code>

Now explain ONLY the numbered chunks below. Each chunk is a real, exact slice of that file.

{blocks}

Respond with JSON exactly matching this shape:

{{
  "explanations": [
    {{"id": <the chunk id as a number>,
      "title": "A short plain-English label for what this chunk does (max 8 words, no code words)",
      "explanation": "1-4 sentences explaining this chunk to someone who has never coded. Say what it does and why it is needed here.",
      "connects_to": "One sentence: where the information in this chunk came from, or where it goes next in the file. Use an empty string if it stands alone."
    }}
  ]
}}

Return one entry for every chunk id given, in the same order. Do not merge or skip chunks.
"""
