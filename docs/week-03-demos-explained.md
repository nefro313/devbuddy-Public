# Week 3 Demos — What Each One Does, Shows, and Teaches

A walkthrough of the four RAG demo scripts in `python/scripts/week-03/`.
Each section covers: **what the script does**, **what you actually see**,
**why the behaviour is that way**, and **the learning you should take away**.

The numbers quoted below are from a typical run against the current corpus
(`shared/data/`) with the current embedding model (`all-MiniLM-L6-v2`) and
`gpt-4o-mini` via OpenRouter. Scores and chunk counts can shift if the corpus,
chunking rules, or model change — but the *mechanisms* they illustrate do not.

> **Prerequisites:** Qdrant running (`docker-compose up -d`), `.env` configured
> with `OPENROUTER_API_KEY`, and dependencies installed. The demos rebuild the
> `devbuddy-docs` collection on every run, so they are self-contained.

---

## The four demos at a glance

| Demo | Concept | The one-line lesson |
|------|---------|---------------------|
| 01 — Embed → Retrieve → Ground | The full RAG loop, made inspectable | Grounding (precision) and recall are **different** failures |
| 02 — Hallucinate → Ground | Guardrails + relevance gates | Retrieval always guesses; you decide when "no match" is allowed |
| 03 — Chunk size | How chunking changes retrieval | Chunk size reshuffles *which chunks exist*, and top-k fills empty slots with noise |
| 04 — Hybrid search | BM25 + vector fused via RRF | Vector finds meaning, BM25 finds exact tokens — and neither is enough alone |

---

## Demo 1 — Embed → Retrieve → Ground

Run:

```bash
python scripts/week-03/demo-01-embed-retrieve-ground.py
```

### What it does

1. Indexes `shared/data/` into Qdrant (chunk size 512, overlap 64).
2. Embeds the question *"What endpoints does the payment API expose?"* into a
   384-dimensional vector.
3. Retrieves the 4 closest chunks by cosine similarity.
4. Injects those chunks **verbatim** into `SYSTEM_PROMPT` and asks the LLM to
   answer.
5. Runs two automated checks on the answer: a **grounding check** and a
   **recall check**.

### What you see

- `✅ Indexed 17 chunks` (not 19 — see the note below).
- The top-4 chunks, with scores:
  ```
  [1] payment-api-spec.md  (score=0.459)   ## Authentication …
  [2] payment-api-spec.md  (score=0.345)   ## Endpoints …
  [3] incident-log.md       (score=0.312)   # Production Incidents …
  [4] ambiguous-diff.txt    (score=0.295)   Update payment processing timeout
  ```
- The **real** prompt — the actual context, not a placeholder.
- An answer that lists three endpoints.
- Two verdicts:
  ```
  ✅ All 3 endpoint claim(s) appear in the retrieved context.
  ⚠️  1 of 4 spec endpoint(s) were never retrieved: /v1/payments/health
  ```

### Why the behaviour is so

- **Scores are cosine similarity** between the query vector and each chunk
  vector. Higher = more similar. For this corpus, genuinely relevant chunks sit
  around 0.4–0.6 and irrelevant ones around 0.2–0.3.
- **The title-only chunk no longer wins.** A previous version returned a bare
  `# Payment API — Internal Specification` heading as rank 1. Heading-plus-
  metadata chunks with no body are now dropped at index time, so the top slot
  goes to actual content.
- **The answer lists 3 endpoints, not 4.** The `GET /v1/payments/health` chunk
  scores below the 4th slot and is never retrieved. The model does not
  hallucinate the 4th endpoint — it never saw it. That is the difference
  between:
  - **Grounding / precision** — every claim in the answer is backed by the
    retrieved context. ✅ passes.
  - **Recall** — everything relevant in the corpus made it into the context. ❌
    fails here (1 of 4 endpoints missing).

### The learning

- The RAG loop is not magic: **embed → retrieve → ground** is three steps you
  can (and should) inspect individually.
- **Check the evidence, not the model's confidence.** The chunks are the ground
  truth; the answer is a projection of them.
- **Precision ≠ recall.** A grounded answer can still be incomplete. "No
  hallucination" is not the same as "complete answer." In production you need to
  fix retrieval gaps (raise `k`, better chunking, query rewriting), not the
  prompt.

---

## Demo 2 — Hallucinate → Ground

Run:

```bash
python scripts/week-03/demo-02-hallucinate-ground.py
```

### What it does

Holds the question and retrieved chunks fixed, then changes only what the
system does with them:

1. Asks an **out-of-corpus** question — *"What's the revenue forecast for Q4
   2028?"* — and shows that retrieval still returns its top-3.
2. Applies a **relevance gate** (`min_score=0.35`) and shows the same query
   returns nothing.
3. Answers with the **guardrail prompt** (`SYSTEM_PROMPT`).
4. Answers with the **no-guardrail prompt** (`NO_GUARDRAIL_PROMPT`), which
   removes the grounding instruction and invites assumptions.
5. Answers an **in-corpus** question to show grounded behaviour.
6. Prints a `Verdict:` line classifying what the model *actually* did.

### What you see

- Out-of-corpus retrieval returns three irrelevant chunks (scores ~0.265 /
  0.225 / 0.215) — none mention revenue or 2028.
- The relevance gate:
  ```
  Now set a cutoff: min_score=0.35. The same query returns
  0 chunk(s) — 'no match' becomes a first-class answer
  ```
- With the guardrail:
  ```
  Answer: I don't have information about that in my knowledge base.
  Verdict: REFUSAL — declines to answer
  ```
- Without the guardrail (with the current model):
  ```
  Answer: I don't have any information about revenue forecasts for Q4 2028…
  Verdict: REFUSAL — declines to answer
  ```
- In-corpus:
  ```
  Answer: To contribute code to DevBuddy, follow these steps…
  Verdict: GROUNDED / OTHER — answer appears tied to context
  ```

### Why the behaviour is so

- **Vector search has no "not found".** It is a *top-k nearest-neighbour*
  query: it must return `k` chunks, even when the query points into an empty
  region of vector space. Similarity is a **relative ranking**, not an
  **absolute relevance judgement**.
- **`min_score` turns "best guess" into "no match."** Below the cutoff, chunks
  are dropped. The score cliff (~0.27 vs ~0.6) is what makes a cutoff possible
  — but the right threshold is corpus-specific and must be measured.
- **The guardrail prompt tells the model to decline.** `SYSTEM_PROMPT` says
  "answer using ONLY the provided context … say 'I don't have information'."
- **Removing the guardrail does *not* guarantee a hallucination.** With
  `gpt-4o-mini`, the unguarded prompt still refuses (just more verbosely). The
  demo now *classifies* the observed behaviour instead of asserting it, because
  this outcome is model-dependent. A smaller or less-aligned model may well
  invent an answer under the same unguarded prompt — that's the `YOUR TURN`
  experiment at the end.

### The learning

- **Retrieval always guesses; you decide whether that's acceptable.** A
  relevance cutoff is the retrieval-side fix; a guardrail is the generation-side
  fix. They address the same failure at different layers.
- **The guardrail is one line of defence, not the whole story.** The current
  model refuses even without it — but you cannot rely on that. Measure what
  *your* model does, then design for it.
- **Classify, don't assert.** A demo that prints the actual verdict (REFUSAL /
  HALLUCINATION / GROUNDED) teaches more than a scripted "it hallucinates."

---

## Demo 3 — Chunk Size

Run:

```bash
python scripts/week-03/demo-03-chunk-size.py
```

### What it does

Indexes the same documents three times — chunk size 256, 512, 1024 — and
retrieves the top-3 chunks for the **same** question each time:

> "How do I set up DevBuddy?"

Only the chunk size changes. The question, embeddings, and retriever are
identical.

### What you see

| chunk_size | chunks indexed | what the top-3 looks like |
|------------|----------------|---------------------------|
| 256 | 34 | Setup chunk (0.398), then a payment-api chunk leaks in (0.227) |
| 512 | 17 | All three from `CONTRIBUTING.md` (0.403 / 0.250 / 0.239) |
| 1024 | 10 | First chunk is large and on-topic, but slot 3 is the whole payment spec (828 chars) |

- At 256, the question's answer is split across more chunks; a payment chunk
  fills the vacant slot 3.
- At 512, the three retrieved chunks all come from the correct document.
- At 1024, the whole unrelated payment spec rides along in slot 3.

### Why the behaviour is so

- **Smaller chunks → more chunks.** 256 produces 34 chunks; 1024 produces 10.
  More chunks means a finer-grained index, but also more places for context to
  be split (a heading separated from its body).
- **The retriever must return exactly `k`.** Once the genuinely relevant chunks
  run out, the remaining slots are filled by whatever is vector-closest next —
  even if that's an unrelated document.
- **Chunk size doesn't make content more or less relevant.** It reshuffles
  *which chunks exist*, and therefore which unrelated chunk lands in a vacant
  top-3 slot. That's why the noise appears at different sizes for the same
  question.

### The learning

- **There is no universal chunk size.** The sweet spot depends on document
  structure, question length, and how much context an answer needs. The demo
  prints the evidence so you can decide — it does not tell you the answer.
- **Top-k with no relevance gate will always leak noise.** If your retriever
  must return `k`, it will fill every slot with something. Chunk size just
  changes *which* noise leaks in.
- **Measure, don't guess.** The summary table (chunks indexed, average
  retrieved length) is the kind of evidence you should collect for your own
  corpus before choosing a chunk size.

---

## Demo 4 — Hybrid Search (RRF fusion)

Run:

```bash
python scripts/week-03/demo-04-hybrid-search.py
```

### What it does

Runs two retrievers over the same index and fuses their rankings with RRF
(reciprocal rank fusion):

- **Vector** — matches meaning (synonyms, paraphrases).
- **BM25** — matches exact tokens (IDs, codes, names).

For each query it prints the vector-only top-5, then a **fusion table** showing
each result's rank in both retrievers and its fused RRF score.

### What you see

For the natural-language query *"how do I set up DevBuddy?"* both retrievers
agree and the top result is `CONTRIBUTING.md`.

For the exact-ID query **`INC-799`**:

- Vector-only **misses the exact ticket entirely** — its top-5 are INC-901,
  the inventory SLA, a deploy log, the incident index, and a recommendation.
- The fusion table then shows:
  ```
  [3] vec=6   bm25=1    rrf=0.0315   ## INC-799 — auth-service token validation failure
  ```
  The exact match is **surfaced by BM25 but fused to #3**, beaten by INC-901
  (`vec=1, bm25=3`).

### Why the behaviour is so

- **Vector search matches meaning.** The embedding for `"INC-799"` is
  semantically near *other incident/ticket content*, not near the specific
  ticket — so the exact ticket ranks 6th on the vector side.
- **BM25 matches exact tokens.** The tokenizer now lowercases and splits on
  non-alphanumerics, so `INC-799` → `["inc", "799"]` and BM25 correctly ranks
  the exact ticket **#1**. (An earlier version used `text.split()`, which kept
  the hyphen and case, so almost nothing matched — that's a real lesson in
  tokenization.)
- **RRF sums the two ranks:**
  ```
  rrf = 1/(60 + vec_rank) + 1/(60 + bm25_rank)
  ```
  INC-901 gets `1/61 + 1/63 = 0.0323`; INC-799 gets `1/66 + 1/61 = 0.0315`.
  Because RRF weights both sides equally, the vector side's strong preference
  for INC-901 beats BM25's strong preference for the exact ticket.
- **"Blind spot" rows** show where one retriever never ranked a chunk at all —
  that's the gap hybrid search exists to close.

### The learning

- **Vector = meaning; BM25 = exact tokens.** They have complementary blind
  spots. Ticket IDs, error codes, version strings (`INC-799`, `402`, `v1.8.2`)
  have no useful semantic neighbours, so vector buries them.
- **Hybrid surfaces what one side misses, but does not guarantee #1.** In this
  run hybrid brought `INC-799` into the top-3 when vector-only missed it
  entirely — that's the win. It did *not* promote it to #1 because RRF weighs
  both retrievers equally. If exact IDs must win, that's a design decision
  (weight BM25 higher, or add a score gate) with a cost.
- **RRF needs no tuning** (`K=60` is a sane default) and BM25 is cheap to run —
  which is why hybrid is a reasonable production default.

---

## How to read the numbers

- **`score=`** in demos 1–3 is cosine similarity: higher = more similar. The
  useful range for this corpus is roughly 0.2–0.6.
- **`vec=` / `bm25=`** in demo 4 are 1-based ranks in each retriever's
  candidate list; `—` means that retriever never ranked the chunk.
- **`rrf=`** is the fused score: the sum of `1/(60 + rank)` across both
  retrievers. It's a ranking aid, not a probability.

## The interactive elements

Each demo now includes:

- **`PAUSE & PREDICT`** — a prompt to form a hypothesis *before* the reveal.
  Prediction-then-reveal is what turns reading into learning.
- **A machine-run check** (demo 1's grounding + recall, demo 2's verdicts) so
  the lesson is demonstrated mechanically, not just asserted.
- **`YOUR TURN`** — a concrete follow-up experiment (change the question, the
  model, the chunk size, or the query tokens) with something specific to look
  for.

If you only have time for one pass, run each demo once, read the `PAUSE &
PREDICT` line, guess, then check your guess against the output. That single
habit — predict, then observe — is the meta-lesson of all four scripts.

---

## Note on chunk counts

`index_documents()` now drops heading-only chunks (a bare `# Title` plus
date/owner metadata) at index time. At chunk size 512 this yields **17 chunks**
rather than the 19 that older versions of the walkthrough (and `week-03.md`)
may reference. The filter is deliberate: those heading chunks scored high on
similarity while carrying no answer content.
