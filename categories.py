"""
categories.py - the ONE place the category list lives.

Person C (storage.py) uses CATEGORIES for folder names.
Person A (ai_analyses.py) uses it to tell the AI what it may choose from.

The list is NOT final, so just edit it here. Everyone else picks up the change
automatically because they import from this file.

Rules for editing:
  - Keep names short and filesystem-safe (letters, numbers, spaces, no slashes).
  - Keep "Other" - it is the fallback when the AI is unsure or fails.
  - Add a one-line hint for each category in CATEGORY_HELP. The AI reads these,
    and good hints matter more than anything else for classification quality.
"""

FALLBACK_CATEGORY = "Other"

# Order here is just display order.
CATEGORIES = [
    "Diagrams",
    "Code",
    "Questions",
    "Lecture Notes",
    "Receipts",
    "Other",
]

# Short definitions shown to the AI so similar categories don't get confused.
CATEGORY_HELP = {
    "Diagrams": "Charts, graphs, flowcharts, architecture or scientific figures, drawn illustrations.",
    "Code": "Source code, terminal output, error messages, IDE or editor windows.",
    "Questions": "Exam, homework or quiz questions, problem sheets, things that ask for an answer.",
    "Lecture Notes": "Slides or pages that are mostly text: bullet points, definitions, written notes.",
    "Receipts": "Receipts, invoices, order confirmations, bills, payment screens.",
    "Other": "Anything that does not clearly fit the categories above.",
}

# Sanity check so a typo here fails loudly at import time, not mid-demo.
assert FALLBACK_CATEGORY in CATEGORIES, "FALLBACK_CATEGORY must be in CATEGORIES"
assert set(CATEGORY_HELP) == set(CATEGORIES), "CATEGORY_HELP must have one entry per category"
