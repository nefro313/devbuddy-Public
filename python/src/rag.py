"""
DevBuddy — RAG Pipeline (Week 3)

Ground the model in our documents so it answers from them, not from whatever
it absorbed during training.

The pipeline: load → chunk → embed → store → retrieve → inject → answer.

    index_documents()               build the Qdrant collection
    retrieve(query, k)              top-k semantic search
    hybrid_search(query, k)         vector + BM25, fused with RRF
    grounded_answer(query)          retrieve → inject → answer
    grounded_answer_with_chunks()   the same, plus the evidence

The single most important line in this file is not code — it is the sentence
in ``_GROUNDING_PROMPT`` telling the model to decline when the context does not
contain the answer. Delete it and the same pipeline confidently invents
revenue forecasts. The prompt *is* the guardrail, which is exactly why Week 7
adds a real one that does not depend on the model choosing to cooperate.

Vector store: Qdrant, via docker compose up -d. Dashboard at
http://localhost:6333/dashboard.
Embeddings: all-MiniLM-L6-v2, local and free. ~80MB on first use.

Imports: src.llm (Week 1). Imported by: src.mcp_server (Week 5).
"""

import re
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi

from src.config import settings
from src.llm import get_llm

# Markdown headings first. Splitting on "\n# " matters more than it looks: our
# corpus is one document per file with a single top-level title, so without it
# a whole spec can land in one oversized chunk and drag unrelated sections into
# every result.
_SEPARATORS = ["\n# ", "\n## ", "\n### ", "\n\n", "\n", " ", ""]

_GROUNDING_PROMPT = (
    "You are a knowledge base assistant. Answer the user's question using ONLY "
    "the provided context.\n"
    "If the context does not contain the answer, say \"I don't have information "
    "about that in my knowledge base.\" Never invent information.\n"
    "Do not use prior knowledge. Quote specifics — endpoints, error codes, "
    "dates — exactly as they appear in the context."
)

# Loading the embedding model takes a few seconds, so it is built once per
# process. Week 5's MCP server relies on this: it indexes at startup and every
# later tool call reuses the warm model.
_embeddings: HuggingFaceEmbeddings | None = None
# Chunk texts from the last index in this process. BM25 is lexical and needs
# the corpus in memory; it has no server to query.
_chunk_texts: list[str] = []


class IndexMissingError(RuntimeError):
    """Raised when a search runs before the collection exists."""


# ═══════════════════════════════════════════════════════════════
#  Building the index
# ═══════════════════════════════════════════════════════════════
def get_embeddings() -> HuggingFaceEmbeddings:
    """The embedding model, loaded once per process."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return _embeddings


def load_documents(directory: str | Path | None = None) -> list[Document]:
    """Load every .md and .txt file in ``directory`` (default: shared/data/).

    JSON fixtures are skipped on purpose — service-readiness-*.json is Week 2's
    schema material, not prose worth embedding.
    """
    directory = Path(directory) if directory else settings.data_dir
    if not directory.is_dir():
        raise FileNotFoundError(f"Document directory not found: {directory}")

    documents: list[Document] = []
    for pattern in ("**/*.md", "**/*.txt"):
        loader = DirectoryLoader(
            str(directory),
            glob=pattern,
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=False,
        )
        documents.extend(loader.load())
    return documents


def chunk_documents(
    documents: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """Split documents into overlapping chunks along markdown boundaries."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
        separators=_SEPARATORS,
    )
    return splitter.split_documents(documents)


def index_documents(
    directory: str | Path | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> int:
    """Load, chunk, embed and store the corpus in Qdrant. Returns the chunk count.

    The collection is recreated on every call, so re-indexing at a different
    chunk size replaces the old vectors instead of stacking a second copy
    beside them.
    """
    global _chunk_texts

    chunks = chunk_documents(load_documents(directory), chunk_size, chunk_overlap)
    if not chunks:
        raise ValueError(f"No .md or .txt documents found in {directory or settings.data_dir}")

    QdrantVectorStore.from_documents(
        chunks,
        embedding=get_embeddings(),
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
        force_recreate=True,
    )

    _chunk_texts = [chunk.page_content for chunk in chunks]
    return len(chunks)


def _get_store() -> QdrantVectorStore:
    """Open the existing collection, or explain how to create it."""
    client = QdrantClient(url=settings.qdrant_url)
    if not client.collection_exists(settings.qdrant_collection):
        raise IndexMissingError(
            f"Qdrant collection '{settings.qdrant_collection}' does not exist.\n"
            "Run index_documents() first — and check Qdrant is up: "
            "docker compose up -d"
        )
    return QdrantVectorStore.from_existing_collection(
        embedding=get_embeddings(),
        collection_name=settings.qdrant_collection,
        url=settings.qdrant_url,
    )


# ═══════════════════════════════════════════════════════════════
#  Retrieval
# ═══════════════════════════════════════════════════════════════
def retrieve(query: str, k: int | None = None) -> list[str]:
    """Top-k chunks by semantic similarity."""
    hits = _get_store().similarity_search(query, k=k or settings.retrieval_k)
    return [hit.page_content for hit in hits]


def retrieve_with_scores(query: str, k: int | None = None) -> list[tuple[str, float]]:
    """Top-k chunks with their similarity scores.

    Week 6 needs the score to populate ``Evidence.relevance_score`` — a report
    that cites a chunk should be able to say how well it actually matched.
    """
    hits = _get_store().similarity_search_with_score(query, k=k or settings.retrieval_k)
    return [(hit.page_content, float(score)) for hit, score in hits]


def _bm25_corpus() -> list[str]:
    """Chunk texts for BM25, re-derived from disk in a cold process."""
    global _chunk_texts
    if not _chunk_texts:
        # Chunking is cheap — no embedding calls — so a fresh process can
        # rebuild the lexical side without touching Qdrant.
        _chunk_texts = [c.page_content for c in chunk_documents(load_documents())]
    return _chunk_texts


def _tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric runs.

    Splitting "INC-842" into ("inc", "842") is the point. Whitespace
    tokenisation would keep "INC-842." and "INC-842" as different terms and
    match neither; here the rare token "842" does the work.
    """
    return re.findall(r"[a-z0-9]+", text.lower())


def keyword_search(query: str, k: int | None = None) -> list[str]:
    """Top-k chunks by BM25 lexical relevance, excluding non-matches.

    Uses rank_bm25 directly rather than LangChain's ``BM25Retriever``, because
    that wrapper always returns exactly k documents — including ones scoring
    zero. For a rare term like "INC-842" only one chunk truly matches and the
    rest are corpus-order filler. Fed into RRF, that filler earns real rank
    credit and pushes genuine vector hits out of the results, which makes
    hybrid search measurably *worse* than plain vector search. Dropping
    zero-score hits is what makes the fusion an improvement rather than noise.
    """
    k = k or settings.retrieval_k
    corpus = _bm25_corpus()
    bm25 = BM25Okapi([_tokenize(chunk) for chunk in corpus])
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(range(len(corpus)), key=lambda i: scores[i], reverse=True)
    return [corpus[i] for i in ranked[:k] if scores[i] > 0]


def hybrid_search(query: str, k: int | None = None) -> list[str]:
    """Vector + BM25 keyword search, fused with Reciprocal Rank Fusion.

    Vector search matches meaning. It is poor at tokens that carry no meaning:
    "408", "INC-842", "PROJ-891". Those are exactly the strings an engineer
    pastes in from an alert, so a purely semantic index fails the queries you
    most want it to answer. BM25 covers that gap.

    RRF fuses by rank, not score, which sidesteps the fact that cosine
    similarity and BM25 relevance are not on a comparable scale.
    """
    k = k or settings.retrieval_k

    vector_hits = retrieve(query, k=k)
    keyword_hits = keyword_search(query, k=k)

    # 60 is the constant from the original RRF paper: large enough that the top
    # rank does not dominate, small enough that rank still matters.
    rrf_constant = 60
    scores: dict[str, float] = {}
    for ranking in (vector_hits, keyword_hits):
        for rank, text in enumerate(ranking):
            scores[text] = scores.get(text, 0.0) + 1.0 / (rrf_constant + rank + 1)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [text for text, _ in ranked[:k]]


# ═══════════════════════════════════════════════════════════════
#  Grounded generation
# ═══════════════════════════════════════════════════════════════
def grounded_answer_with_chunks(
    query: str,
    k: int | None = None,
    temperature: float = 0.0,
    use_hybrid: bool = False,
) -> tuple[str, list[str]]:
    """Answer ``query`` from retrieved context. Returns (answer, chunks used).

    Returning the chunks is not a convenience. An answer you cannot trace back
    to its source is indistinguishable from a hallucination that happens to
    sound right.
    """
    chunks = hybrid_search(query, k=k) if use_hybrid else retrieve(query, k=k)
    context = "\n\n---\n\n".join(chunks)

    llm = get_llm(temperature=temperature)
    response = llm.invoke(
        [
            SystemMessage(content=_GROUNDING_PROMPT),
            HumanMessage(content=f"CONTEXT:\n{context}\n\nQuestion: {query}"),
        ]
    )
    return str(response.content).strip(), chunks


def grounded_answer(
    query: str,
    k: int | None = None,
    temperature: float = 0.0,
    use_hybrid: bool = False,
) -> str:
    """Answer ``query`` using only the retrieved context."""
    answer, _ = grounded_answer_with_chunks(
        query, k=k, temperature=temperature, use_hybrid=use_hybrid
    )
    return answer


# ═══════════════════════════════════════════════════════════════
#  Week 3 checkpoint:  python src/rag.py
# ═══════════════════════════════════════════════════════════════
def _rule(title: str) -> None:
    print(f"\n{'─' * 68}\n  {title}\n{'─' * 68}")


def _first_line(chunk: str) -> str:
    for line in chunk.strip().splitlines():
        if line.strip():
            return line.strip()[:70]
    return "(blank)"


def main() -> None:
    print("=" * 68)
    print("  DevBuddy — Week 3: RAG")
    print(f"  corpus     {settings.data_dir}")
    print(f"  qdrant     {settings.qdrant_url} → {settings.qdrant_collection}")
    print(f"  embeddings {settings.embedding_model}")
    print("=" * 68)

    # ── 1. Index ────────────────────────────────────────────────
    _rule("1. index_documents() — load, chunk, embed, store")
    documents = load_documents()
    print(f"  documents loaded  {len(documents)}")
    for doc in documents:
        print(f"     • {Path(doc.metadata['source']).name}")
    count = index_documents()
    print(f"  chunks indexed    {count} (size={settings.chunk_size}, "
          f"overlap={settings.chunk_overlap})")
    print("  → check http://localhost:6333/dashboard")

    # ── 2. Retrieve ─────────────────────────────────────────────
    _rule("2. retrieve() — semantic search over the corpus")
    question = "What endpoints does the payment API expose?"
    print(f"  query: {question}")
    for i, chunk in enumerate(retrieve(question, k=3), 1):
        print(f"     [{i}] {_first_line(chunk)}")

    # ── 3. Grounded answer ──────────────────────────────────────
    _rule("3. grounded_answer() — in-corpus question")
    print(f"  Q: {question}")
    print(f"  A: {grounded_answer(question, k=4)}")

    # ── 4. The guardrail ────────────────────────────────────────
    _rule("4. Out-of-corpus — the system prompt IS the guardrail")
    for probe in (
        "What's the revenue forecast for Q4 2028?",
        "What's the SLA for the inventory service?",
    ):
        answer, chunks = grounded_answer_with_chunks(probe, k=3)
        print(f"\n  Q: {probe}")
        print(f"  A: {answer}")
        print(f"  grounded in {len(chunks)} chunk(s): {_first_line(chunks[0])}")

    # ── 5. Chunk size ───────────────────────────────────────────
    _rule("5. Chunk size changes what retrieval can see")
    setup_question = "How do I contribute to DevBuddy?"
    print(f"  query: {setup_question}\n")
    for size in (256, 512, 1024):
        n = index_documents(chunk_size=size)
        top = retrieve(setup_question, k=1)[0]
        covers_setup = "venv" in top or "requirements.txt" in top
        print(f"  size={size:5}  {n:3} chunks   top hit is {len(top):5} chars   "
              f"includes the setup steps: {covers_setup}")
    print(
        "\n  ↑ the same top document at every size — what changes is how much of\n"
        "    it comes back. At 256 the answer is split across chunks the\n"
        "    retriever did not return; at 1024 you pay for unrelated sections\n"
        "    riding along in the context window."
    )

    # ── 6. Hybrid search ────────────────────────────────────────
    _rule("6. hybrid_search() — where pure vector search fails")
    index_documents()  # back to the default size
    # A commit SHA is the honest test. It carries no meaning for an embedding
    # model to match on, and it is exactly what someone pastes in from an alert.
    keyword_query = "abc123def456"
    print(f"  query: {keyword_query!r} — a deploy SHA, present verbatim in deploy-log.md\n")

    for label, hits in (
        ("vector", retrieve(keyword_query, k=4)),
        ("bm25", keyword_search(keyword_query, k=4)),
        ("hybrid", hybrid_search(keyword_query, k=4)),
    ):
        found = any(keyword_query.lower() in chunk.lower() for chunk in hits)
        mark = "✅" if found else "❌"
        print(f"  {label:7} {len(hits)} hit(s)  {mark} contains the SHA: {found}")
        for i, chunk in enumerate(hits, 1):
            print(f"      [{i}] {_first_line(chunk)}")
        print()

    print(
        "  ↑ vector search returned four confident, entirely wrong chunks — the\n"
        "    string is in the corpus and it never found it. BM25 matched one\n"
        "    chunk and stopped, because only one chunk matched. On a corpus this\n"
        "    small hybrid rarely reorders anything; what it buys you here is\n"
        "    recall on exactly the queries semantic search cannot represent."
    )

    print("\n" + "=" * 68)
    print(f"  Week 3 complete. Collection '{settings.qdrant_collection}' left at "
          f"size={settings.chunk_size}.")
    print("=" * 68)


if __name__ == "__main__":
    main()
