"""
Demo 1: Embed → Retrieve → Ground

The full RAG loop, made inspectable:

  1. EMBED    — every chunk becomes a vector (a point in space)
  2. RETRIEVE — the query is embedded, the closest chunks are returned
  3. GROUND   — those SAME chunks are injected into the prompt, and the
                LLM must answer from them

The point of this demo is not just to see an answer — it is to see the
evidence. Every chunk that grounds the answer is printed with its source,
and the prompt the model actually receives is shown.

Run: python scripts/week-03/demo-01-embed-retrieve-ground.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.rag import (
    DATA_DIR,
    EMBEDDING_MODEL,
    SYSTEM_PROMPT,
    embed_text,
    grounded_answer_from_chunks,
    index_documents,
    retrieve_with_sources,
)

QUESTION = "What endpoints does the payment API expose?"
K = 4

BORDER = "=" * 72


def pause(prompt: str = "  ⏸  Press Enter to continue… ") -> None:
    """Pause so the learner can predict before the reveal.

    Non-interactive runs (piped/CI stdin) skip the pause instead of hanging.
    """
    try:
        input(prompt)
    except EOFError:
        print()


print(BORDER)
print("  Demo 1: Embed → Retrieve → Ground")
print(BORDER)
print()
print("  The RAG loop, step by step:")
print("    1. EMBED    — each chunk → a vector (a point in space)")
print(f"                   model: {EMBEDDING_MODEL} (384-dim vectors)")
print("    2. RETRIEVE — embed the query, return the closest chunks")
print("    3. GROUND   — inject those chunks into the prompt, answer")
print()
print(f"  Question: {QUESTION}")
print()

# ── Step 1: Embed + index ─────────────────────────────────────
print("  ── Step 1: Embed & index ────────────────────────────────")
print()
print("  Each document is split into chunks. Each chunk is embedded")
print("  into a vector and stored in Qdrant.")
print()
count = index_documents(chunk_size=512, chunk_overlap=64)
print(f"  ✅ Indexed {count} chunks → collection 'devbuddy-docs'")
print()

# ── Step 2: Retrieve ──────────────────────────────────────────
print("  ── Step 2: Retrieve (top-k by vector similarity) ────────")
print()
print("  The request — the query — is also embedded into a vector:")
print()
print(f'    "{QUESTION}"')
query_vector = embed_text(QUESTION)
print(f"    → {len(query_vector)}-dim vector: "
      f"{[round(v, 4) for v in query_vector[:5]]} ...")
print()
print(f"  Qdrant returns the {K} chunks whose vectors are closest to")
print("  that query vector, most relevant first. The source and similarity")
print("  score of each chunk are shown so you can trace it back:")
print()
chunks = retrieve_with_sources(QUESTION, k=K)
for i, chunk in enumerate(chunks, 1):
    print(f"  [{i}] {chunk.source}  (score={chunk.score:.3f})")
    print(f"      {chunk.content}")
    print()

print("  ⏸  PAUSE & PREDICT:")
print("     The payment API spec actually defines 4 endpoints. Look at the")
print(f"     {K} chunks above — which endpoint is MISSING from the retrieval?")
print("     Will the answer mention it? Predict, then continue.")
pause()

# ── Step 3: Ground ────────────────────────────────────────────
print("  ── Step 3: Ground (chunks → prompt → LLM) ───────────────")
print()
print("  The chunks above are injected VERBATIM into the system prompt")
print("  as CONTEXT. This is the exact prompt the model receives:")
print()
prompt_preview = SYSTEM_PROMPT.format(
    context="\n\n---\n\n".join(c.content for c in chunks)
)
for line in prompt_preview.splitlines():
    print(f"  │ {line}")
print()
print("  ── user message ──")
print(f"  │ {QUESTION}")
print()

answer = grounded_answer_from_chunks(QUESTION, [c.content for c in chunks], temperature=0.0)
print("  ── answer ──")
print(f"  │ {answer}")
print()

# ── Verify ────────────────────────────────────────────────────
print(BORDER)
print("  Verify the grounding (automated):")
context = "\n".join(c.content for c in chunks)
claims = re.findall(r"\b(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s,`*]+)", answer)
if not claims:
    print("  ⚠️  No endpoint paths detected in the answer — verify by hand.")
else:
    ungrounded = [path for path in claims if path.rstrip(".") not in context]
    if ungrounded:
        print(f"  ❌ {len(ungrounded)}/{len(claims)} endpoint claim(s) NOT in retrieved context:")
        for path in ungrounded:
            print(f"      - {path}")
    else:
        print(f"  ✅ All {len(claims)} endpoint claim(s) appear in the retrieved context.")

# ── Recall check ──────────────────────────────────────────────
print()
print("  Recall check — grounding ≠ completeness:")
spec_path = os.path.join(DATA_DIR, "payment-api-spec.md")
with open(spec_path) as f:
    spec_text = f.read()
all_endpoints = re.findall(r"\b(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s,`*]+)", spec_text)
missing = [e for e in all_endpoints if e.rstrip(".") not in context]
if missing:
    print(f"  ⚠️  {len(missing)} of {len(all_endpoints)} spec endpoint(s) were never retrieved:")
    for e in missing:
        print(f"      - {e}")
    print("     The model didn't hallucinate — it never SAW these. This is a")
    print("     RECALL gap (retrieval missed evidence), not a grounding failure")
    print("     (answer claims evidence that isn't there). Different bug, different fix.")
else:
    print(f"  ✅ All {len(all_endpoints)} spec endpoint(s) were retrieved.")
print(BORDER)
