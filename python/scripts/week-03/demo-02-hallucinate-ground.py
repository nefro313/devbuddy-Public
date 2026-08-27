"""
Demo 2: Hallucinate → Ground

The system prompt is the guardrail. This demo holds the question AND the
retrieved chunks fixed and changes only the system prompt, then classifies
what the model actually does:

  1. OUT-OF-CORPUS + guardrail   → expected: the model declines
  2. OUT-OF-CORPUS, no guardrail → expected: it may invent an answer
  3. IN-CORPUS + guardrail       → expected: the model answers from chunks

The demo prints a Verdict for each answer instead of assuming a narrative —
the actual behaviour depends on the model in .env, so classify, don't assert.

Run: python scripts/week-03/demo-02-hallucinate-ground.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.rag import (
    NO_GUARDRAIL_PROMPT,
    SYSTEM_PROMPT,
    answer_with_context,
    index_documents,
    retrieve_with_sources,
)

OUT_OF_CORPUS = "What's the revenue forecast for Q4 2028?"
IN_CORPUS = "How do I contribute code to DevBuddy?"
K = 3
BORDER = "=" * 72


def classify_answer(answer: str, chunks: list[str]) -> str:
    """Classify what the model actually did, instead of asserting a narrative."""
    joined = "\n".join(chunks).lower()
    low = answer.lower()
    # Refusal signals — checked first: a refusal that echoes the question's
    # terms ("revenue forecast for Q4 2028") is still a refusal, not a
    # hallucination.
    if any(t in low for t in (
        "don't have information",
        "don't have any information",
        "do not have information",
        "does not contain",
        "no information",
        "no financial",
        "i don't know",
        "cannot answer",
        "can't answer",
        "don't have access",
        "do not have access",
        "i'm sorry, but i don't have",
        "i'm sorry, but i cannot",
    )):
        return "REFUSAL — declines to answer"
    # Question terms absent from context: the model can only assert them by
    # inventing them.
    if any(t in low for t in ("revenue", "forecast", "2028", "q4")) and "2028" not in joined:
        return "HALLUCINATION — claims something the context never mentions"
    return "GROUNDED / OTHER — answer appears tied to context"


def pause(prompt: str = "  ⏸  Press Enter to continue… ") -> None:
    """Pause so the learner can predict before the reveal.

    Non-interactive runs (piped/CI stdin) skip the pause instead of hanging.
    """
    try:
        input(prompt)
    except EOFError:
        print()


print(BORDER)
print("  Demo 2: Hallucinate → Ground")
print(BORDER)
print()

index_documents(chunk_size=512, chunk_overlap=64)
print("  ✅ Index ready")
print()

# ── The out-of-corpus retrieval ───────────────────────────────
# WHY does the retriever return "random" info for an out-of-corpus
# question ("Q4 2028 revenue") instead of nothing?
#
# Because vector search is a top-k nearest-neighbour query: it ALWAYS
# returns k chunks and has no "not found" concept and no relevance
# cutoff. For this question the query vector points into an empty
# region of vector space, so the "nearest" chunks are still far away
# (see the scores printed below — roughly 0.28 / 0.26 / 0.21, versus
# ~0.60 for an in-corpus question) and happen to be about payments,
# incidents and SLAs.
#
# Similarity is a RELATIVE ranking, not an ABSOLUTE relevance
# judgement: Qdrant sorts everything by distance and hands back the
# top-k. It never says "0.22 is too low to be useful — nothing
# matched". That decision is left to the guardrail below.
print(f'  Out-of-corpus question: "{OUT_OF_CORPUS}"')
print()
print(f"  The retriever always returns its top-{K} chunks — even when none")
print("  of them answer the question:")
print()
chunks = retrieve_with_sources(OUT_OF_CORPUS, k=K)
for i, c in enumerate(chunks, 1):
    print(f"  [{i}] {c.source}  (score={c.score:.3f})")
    print(f"      {c.content}")
    print()
print('  None of these mention Q4 2028 revenue. Retrieval can\'t return')
print('  "nothing" — it returns its best (irrelevant) guess.')
print()

# ── The relevance gate ────────────────────────────────────────
print("  ── The relevance gate (min_score) ────────────────────────")
print()
print("  Now set a cutoff: min_score=0.35. The same query returns")
gated = retrieve_with_sources(OUT_OF_CORPUS, k=K, min_score=0.35)
print(f"  {len(gated)} chunk(s) — 'no match' becomes a first-class answer")
print("  instead of a best guess.")
print()

# ── With the guardrail ────────────────────────────────────────
print("  ── With the guardrail ───────────────────────────────────")
print()
print("  The system prompt tells the model to decline when the context")
print("  doesn't contain the answer:")
print()
for line in SYSTEM_PROMPT.format(context=f"<the {K} chunks above>").splitlines():
    print(f"  │ {line}")
print()
guarded = answer_with_context(OUT_OF_CORPUS, [c.content for c in chunks], SYSTEM_PROMPT)
print(f"  Answer: {guarded}")
print(f"  Verdict: {classify_answer(guarded, [c.content for c in chunks])}")
print()

# ── Without the guardrail ─────────────────────────────────────
print("  ── Without the guardrail ────────────────────────────────")
print()
print("  Same question, same chunks — but the prompt no longer grounds the")
print("  model to the context and invites it to make assumptions.")
print()
print("  ⏸  PAUSE & PREDICT: will it invent an answer, or refuse anyway?")
pause()
print()
for line in NO_GUARDRAIL_PROMPT.format(context=f"<the {K} chunks above>").splitlines():
    print(f"  │ {line}")
print()
unguarded = answer_with_context(OUT_OF_CORPUS, [c.content for c in chunks], NO_GUARDRAIL_PROMPT)
print(f"  Answer: {unguarded}")
print(f"  Verdict: {classify_answer(unguarded, [c.content for c in chunks])}")
print()

# ── In-corpus ─────────────────────────────────────────────────
print("  ── In-corpus (grounded) ─────────────────────────────────")
print()
print(f'  Question: "{IN_CORPUS}"')
print()
grounded_chunks = retrieve_with_sources(IN_CORPUS, k=K)
for i, c in enumerate(grounded_chunks, 1):
    print(f"  [{i}] {c.source}  (score={c.score:.3f})")
    print(f"      {c.content}")
    print()
grounded = answer_with_context(IN_CORPUS, [c.content for c in grounded_chunks], SYSTEM_PROMPT)
print(f"  Answer: {grounded}")
print(f"  Verdict: {classify_answer(grounded, [c.content for c in grounded_chunks])}")
print()

print(BORDER)
print("  Same retriever. Same chunks. Only the system prompt changed.")
print("  Read the Verdict lines above: with the current model the guarded")
print("  prompt produces a terse refusal, while the unguarded prompt may")
print("  refuse more helpfully or — if the model follows the invitation —")
print("  invent an answer. Classify, don't assume.")
print()
print("  YOUR TURN:")
print("    • Change OUT_OF_CORPUS to something plausible but absent")
print("      (e.g. 'What is the auth-service SLA?') and re-run. Predict")
print("      the verdict for each prompt before reading it.")
print("    • Point .env at a smaller local model. Does the unguarded")
print("      prompt finally hallucinate? Why does model size matter here?")
print(BORDER)
