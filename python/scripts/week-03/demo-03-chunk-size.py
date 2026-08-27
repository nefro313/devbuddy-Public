"""
Demo 3: Chunking — how chunk size changes what gets retrieved

Indexes the same documents three times — chunk size 256, 512, 1024 — and
retrieves the top-3 chunks for the SAME question each time. Only the chunk
size changes; the question, the embeddings, and the retriever are identical.

Watch two things at each size:
  • how many chunks the index holds (smaller chunks → more chunks)
  • which documents the retrieved chunks come from, and how long they are

Run: python scripts/week-03/demo-03-chunk-size.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.rag import index_documents, retrieve_with_sources

QUESTION = "How do I set up DevBuddy?"
# The answer to this question lives in CONTRIBUTING.md — so chunks from
# other files are noise. (This is a fact about the corpus, not a verdict.)
ANSWER_DOC = "CONTRIBUTING.md"
K = 3
SIZES = [256, 512, 1024]


def pause(prompt: str = "  ⏸  Press Enter to continue… ") -> None:
    """Pause so the learner can predict before the reveal.

    Non-interactive runs (piped/CI stdin) skip the pause instead of hanging.
    """
    try:
        input(prompt)
    except EOFError:
        print()


print("=" * 72)
print("  Demo 3: Chunk Size — Same Question, Different Retrieval")
print("=" * 72)
print()
print(f'  Question: "{QUESTION}"')
print()
print("  The documents are indexed three times, once per chunk size.")
print("  The question and the retriever do not change — only chunk size.")
print()
print(f"  The answer to this question lives in {ANSWER_DOC};")
print("  chunks from other files are noise.")
print()

# Why do unrelated docs (e.g. payment-api-spec.md) appear in the results?
#
# The retriever is a top-k nearest-neighbour search: it must return exactly
# K chunks and has NO relevance gate. For this question the genuinely close
# chunks are all in CONTRIBUTING.md (see the scores printed below). Once
# those run out, slot K gets filled by whatever is vector-closest next — and
# that is payment-api-spec.md (incident-log scores lower still).
#
# "Closest in embedding space" ≠ "topically relevant". The score cliff
# (0.40 → 0.17) is the retriever's way of saying "best I have left".
#
# Chunk size decides HOW the noise leaks in:
#   • 256/1024 → only 2 CONTRIBUTING chunks outscore payment-api-spec.md,
#     so it slips into slot 3 (as a 199-char endpoint shard or the whole
#     828-char spec).
#   • 512      → exactly 3 CONTRIBUTING chunks outscore it, so it lands at
#     slot 4 and stays invisible.
#
# The chunk itself doesn't get more relevant — chunk size just reshuffles
# which chunks exist, and a vacant top-K slot gets filled with noise.

print("  ⏸  PAUSE & PREDICT: at which chunk size does a non-CONTRIBUTING")
print("     document first leak into the top-3? Guess before reading.")
pause()
print()

summary = []

for size in SIZES:
    count = index_documents(chunk_size=size, chunk_overlap=64)
    chunks = retrieve_with_sources(QUESTION, k=K)
    avg_len = sum(len(c.content) for c in chunks) // len(chunks) if chunks else 0

    summary.append((size, count, avg_len))

    print(f"  ── chunk_size = {size}   ({count} chunks indexed) ──")
    print()
    for i, c in enumerate(chunks, 1):
        note = "" if c.source == ANSWER_DOC else "   ← other document"
        print(f"  [{i}] {c.source}  ({len(c.content)} chars, score={c.score:.3f}){note}")
        print(f"      {c.content}")
        print()
    print()

# ── Summary ──────────────────────────────────────────────────
print("=" * 72)
print("  SUMMARY")
print("=" * 72)
print()
print(f"  {'chunk_size':<12} {'chunks indexed':<16} {'avg retrieved len':<20}")
print(f"  {'─' * 12} {'─' * 16} {'─' * 20}")
for size, count, avg_len in summary:
    print(f"  {size:<12} {count:<16} {avg_len:<20}")
print()
print("  The tradeoff, in general:")
print("    smaller → more chunks, each tighter, but context can be split")
print("              (e.g. a bare '# Title' with no body).")
print("    larger  → fewer chunks, but unrelated content can ride along")
print("              (e.g. a whole payment API spec in a setup answer).")
print()
print("  Look back at the sources and lengths above and decide where the")
print("  balance sits for THESE documents. There is no universal answer.")
print()
print("  YOUR TURN:")
print("    • Change QUESTION to 'What is the payment API SLA?' and re-run.")
print("      Which chunk size keeps the answer self-contained? Why?")
print("    • Add chunk_size=2048 to SIZES. Predict what happens to the")
print("      'unrelated content rides along' problem before you run.")
print("=" * 72)
