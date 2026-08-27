"""
Demo 4: Hybrid Search — the RRF fusion table

Vector search matches MEANING; BM25 matches EXACT TERMS (IDs, codes,
names). Hybrid runs both and merges the rankings with RRF. This demo
prints the fusion table so you can see each retriever's rank for every
result — and where each side has a blind spot.

Run: python scripts/week-03/demo-04-hybrid-search.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.rag import RRF_K, hybrid_search_with_scores, index_documents, retrieve

index_documents(chunk_size=512, chunk_overlap=64)

# Add your own queries here to explore the tradeoff.
QUERIES = [
    ("how do I set up DevBuddy?", "natural language"),
    ("INC-799", "exact ticket ID"),
]
def first_line(text: str) -> str:
    return text.strip().split("\n")[0]


def rrf(rank: int | None) -> float:
    """One retriever's contribution to the fused score (0 if it missed the chunk)."""
    return 1.0 / (RRF_K + rank) if rank else 0.0


def pause(prompt: str = "  ⏸  Press Enter to continue… ") -> None:
    """Pause so the learner can predict before the reveal.

    Non-interactive runs (piped/CI stdin) skip the pause instead of hanging.
    """
    try:
        input(prompt)
    except EOFError:
        print()


print("=" * 72)
print("  Demo 4: Hybrid Search — the RRF fusion table")
print("=" * 72)
print()

print("  ⏸  PAUSE & PREDICT: for 'INC-799', will vector-only find the")
print("     exact ticket? Will hybrid rank it #1? Guess before reading.")
pause()
print()

for question, kind in QUERIES:
    vec = retrieve(question, k=5)
    fused = hybrid_search_with_scores(question, k=5)

    print(f'  Query: "{question}"   ({kind})')
    print()

    print("  ▸ VECTOR ONLY (semantic) — what the vector search alone returns:")
    for i, c in enumerate(vec, 1):
        print(f"    [{i}] {first_line(c)}")
    print()

    print("  ▸ THE FUSION TABLE — how hybrid re-ranks the results.")
    print("    vec = rank in the vector top-10, bm25 = rank in the BM25 top-10,")
    print("    '—' = that retriever never ranked this chunk (a blind spot).")
    print(f"    rrf = sum of 1/({RRF_K} + rank) across both sides.")
    print()
    for i, r in enumerate(fused, 1):
        vr = str(r.vec_rank) if r.vec_rank else "—"
        br = str(r.bm25_rank) if r.bm25_rank else "—"
        print(f"    [{i}] vec={vr:<3} bm25={br:<4} rrf={r.rrf_score:.4f}   {first_line(r.content)}")
        print(f"          source: {r.source}")
    print()

    # Spell out the math for every row where one retriever had a blind spot.
    blind = [r for r in fused if not r.vec_rank or not r.bm25_rank]
    if blind:
        print("  Blind spots (this is why hybrid exists):")
        for r in blind:
            vr = r.vec_rank if r.vec_rank else "—"
            br = r.bm25_rank if r.bm25_rank else "—"
            vc = f"1/{RRF_K + r.vec_rank} = {rrf(r.vec_rank):.4f}" if r.vec_rank else "nothing (vector missed it)"
            bc = f"1/{RRF_K + r.bm25_rank} = {rrf(r.bm25_rank):.4f}" if r.bm25_rank else "nothing (BM25 missed it)"
            print(f"    • {first_line(r.content)}")
            print(f"      vector {vr} → {vc};  BM25 {br} → {bc};  total rrf = {r.rrf_score:.4f}")
        print()
    print()

print("=" * 72)
print("  PRACTICAL GUIDE")
print("=" * 72)
print()
print("  • Vector-only is fine when users ask natural-language questions")
print("    with synonyms and paraphrases (\"how do I set this up?\").")
print()
print("  • Hybrid earns its keep when queries carry exact tokens:")
print("    ticket IDs, error codes, service names, version strings")
print("    (\"INC-799\", \"auth-service\", \"v1.8.2\") — terms with no")
print("    semantic neighbours that vector ranking buries. It surfaces")
print("    them (vector-only missed INC-799 above), though RRF may not")
print("    promote them to #1 when the vector side strongly disagrees.")
print()
print("  • RRF needs no tuning (K={RRF_K} is a good default) and BM25 is")
print("    cheap to run offline — hybrid is the safe default in")
print("    production retrieval.")
print()
print("  YOUR TURN:")
print("    • Add a query for an exact version string ('v1.8.2') or error")
print("      code ('402'). Predict which retriever wins the #1 slot.")
print("    • The INC-799 exact match landed at #3 because vector ranked it")
print("      low. What change would push it to #1 — and what's the cost?")
print("=" * 72)
