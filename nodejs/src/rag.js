/**
 * Week 3 — RAG Pipeline: Embed, Chunk, Store, Retrieve, Ground (Node.js)
 *
 * Uses @xenova/transformers (all-MiniLM-L6-v2) for embeddings — local, free, no API cost.
 * Qdrant for vector storage — runs in Docker, cross-language.
 * Hybrid search with BM25 + vector for exact keyword matching.
 *
 * Imports: import { getLlm } from "./llm.js"
 */
import { readFileSync, readdirSync } from "fs";
import { resolve, extname, dirname } from "path";
import { fileURLToPath } from "url";
import { HuggingFaceTransformersEmbeddings } from "@langchain/community/embeddings/huggingface_transformers";
import { RecursiveCharacterTextSplitter } from "langchain/text_splitter";
import { QdrantVectorStore } from "@langchain/qdrant";
import { QdrantClient } from "@qdrant/js-client-rest";
import { Document } from "@langchain/core/documents";
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { getLlm } from "./llm.js";

// ─── Config ───────────────────────────────────────────────────
// Display name used in demos; the HF hub id used for download is
// Xenova/all-MiniLM-L6-v2 (the "Xenova/" prefix is a transformers.js
// packaging convention, not part of the model itself).
export const EMBEDDING_MODEL = "all-MiniLM-L6-v2";
const _EMBEDDING_MODEL_ID = "Xenova/all-MiniLM-L6-v2";
const QDRANT_URL = process.env.QDRANT_URL || "http://localhost:6333";
const QDRANT_COLLECTION = "devbuddy-docs";
const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = resolve(__dirname, "..", "..", "shared", "data");

// RRF fusion constant — single source of truth (demo-04 imports this).
export const RRF_K = 60;

// The system prompt is the guardrail: it constrains the model to the
// retrieved context and tells it to decline out-of-corpus questions.
export const SYSTEM_PROMPT =
  "You are a knowledge base assistant. Answer the user's question " +
  "using ONLY the provided context below. If the context does not " +
  "contain the answer, say 'I don't have information about that in " +
  "my knowledge base.' Never invent information.\n\n" +
  "CONTEXT:\n" +
  "{context}";

// The SAME prompt with the guardrail removed — used to show what happens
// without it (the model is no longer told to decline).
export const NO_GUARDRAIL_PROMPT =
  "You are a helpful assistant. Answer the user's question, even if you " +
  "have to make reasonable assumptions. Be specific.\n\n" +
  "CONTEXT:\n" +
  "{context}";

let _embeddings = null;
let _vectorstore = null;
let _documents = null;

// ─── Helpers ──────────────────────────────────────────────────

async function _getEmbeddings() {
  if (!_embeddings) {
    _embeddings = new HuggingFaceTransformersEmbeddings({
      model: _EMBEDDING_MODEL_ID,
    });
  }
  return _embeddings;
}

function _tokenize(text) {
  return text.toLowerCase().match(/[a-z0-9]+/g) || [];
}

function _isTitleOnly(text) {
  /**
   * True if a chunk is only a heading + blockquote metadata (no body).
   * Header chunks score high in vector search but carry no answer content.
   */
  const bodyWords = [];
  for (const line of text.split("\n")) {
    const stripped = line.trim();
    if (!stripped || stripped.startsWith("#") || stripped.startsWith(">")) {
      continue;
    }
    bodyWords.push(...stripped.split(/\s+/));
  }
  return bodyWords.length < 8;
}

function _loadDocuments(directory) {
  /**
   * Load .md and .txt files from a directory into Document objects.
   * Returns an array of { pageContent, metadata }.
   */
  const files = [];
  try {
    const entries = readdirSync(directory);
    for (const entry of entries) {
      const ext = extname(entry).toLowerCase();
      if (ext === ".md" || ext === ".txt") {
        const filePath = resolve(directory, entry);
        const content = readFileSync(filePath, "utf-8");
        files.push(
          new Document({
            pageContent: content,
            metadata: { source: entry },
          })
        );
      }
    }
  } catch (e) {
    throw new Error(
      `Failed to load documents from ${directory}: ${e.message}`
    );
  }

  if (files.length === 0) {
    throw new Error(`No .md or .txt files found in ${directory}`);
  }
  return files;
}

// ─── Public API ───────────────────────────────────────────────

/**
 * Load .md and .txt files, chunk them, embed them, and store in Qdrant.
 *
 * @param {string|null} [directory] - Path to document directory. Defaults to shared/data/.
 * @param {number} [chunkSize=512] - Max tokens per chunk.
 * @param {number} [chunkOverlap=64] - Overlapping tokens between chunks.
 * @returns {Promise<number>} Number of chunks indexed.
 */
export async function indexDocuments(
  directory = null,
  chunkSize = 512,
  chunkOverlap = 64
) {
  const target = directory || DATA_DIR;
  const docs = _loadDocuments(target);

  const splitter = new RecursiveCharacterTextSplitter({
    chunkSize,
    chunkOverlap,
    separators: ["\n# ", "\n## ", "\n### ", "\n#### ", "\n", " ", ""],
  });

  const chunks = (await splitter.splitDocuments(docs)).filter(
    (chunk) => !_isTitleOnly(chunk.pageContent)
  );

  const emb = await _getEmbeddings();

  // Delete the collection if it exists to ensure a fresh index
  const client = new QdrantClient({ url: QDRANT_URL });
  try {
    await client.deleteCollection(QDRANT_COLLECTION);
  } catch (e) {
    // Collection might not exist, ignore
  }

  // Connect to Qdrant, recreate collection with fresh vectors
  _vectorstore = await QdrantVectorStore.fromDocuments(chunks, emb, {
    url: QDRANT_URL,
    collectionName: QDRANT_COLLECTION,
  });

  _documents = chunks;
  return chunks.length;
}

/**
 * Retrieve the top-k most relevant chunks for a query.
 *
 * @param {string} query - The search query.
 * @param {number} [k=3] - Number of chunks to return.
 * @returns {Promise<string[]>} List of chunk content strings, most relevant first.
 */
export async function retrieve(query, k = 3) {
  if (!_vectorstore) {
    throw new Error("No index found. Run indexDocuments() first.");
  }
  const results = await _vectorstore.similaritySearch(query, k);
  return results.map((doc) => doc.pageContent);
}

/**
 * Embed a single piece of text into a vector (for inspection / demos).
 *
 * @param {string} text - The text to embed.
 * @returns {Promise<number[]>} The embedding vector.
 */
export async function embedText(text) {
  const emb = await _getEmbeddings();
  return emb.embedQuery(text);
}

/**
 * Retrieve the top-k chunks together with their source document names.
 *
 * @param {string} query - The search query.
 * @param {number} [k=3] - Number of chunks to return.
 * @returns {Promise<Array<{content: string, source: string}>>}
 *   List of { content, source }, most relevant first.
 */
export async function retrieveWithSources(query, k = 3, minScore = null) {
  if (!_vectorstore || !_documents) {
    throw new Error("No index found. Run indexDocuments() first.");
  }
  let results = await _vectorstore.similaritySearchWithScore(query, k);
  if (minScore != null) {
    results = results.filter(([, score]) => score >= minScore);
  }
  const sources = {};
  for (const doc of _documents) {
    sources[doc.pageContent] = doc.metadata?.source || "unknown";
  }
  return results.map(([doc, score]) => ({
    content: doc.pageContent,
    source: sources[doc.pageContent] || doc.metadata?.source || "unknown",
    score,
  }));
}

/**
 * Retrieve using BM25 (keyword) + vector (semantic) and merge via RRF.
 *
 * BM25 catches exact names, IDs, error codes. Vector catches meaning.
 * RRF fusion combines both rankings into one result set.
 *
 * @param {string} query - The search query.
 * @param {number} [k=3] - Number of chunks to return after merging.
 * @returns {Promise<string[]>} List of chunk content strings, merged via RRF.
 */
export async function hybridSearch(query, k = 3) {
  const results = await hybridSearchWithScores(query, k);
  return results.map((r) => r.content);
}

/**
 * hybridSearch() plus the internals: for every final hit, report its
 * rank in EACH retriever (null = that retriever never ranked it) and
 * the fused RRF score.
 *
 * RRF (reciprocal rank fusion): score = sum over retrievers of
 * 1 / (RRF_K + rank). A chunk ranked #1 by BM25 and #7 by vector scores
 * 1/61 + 1/67 — which is why a hit one side ranks #1 can still surface
 * even when the other side ranks it lower.
 *
 * @param {string} query - The search query.
 * @param {number} [k=3] - Number of chunks to return after merging.
 * @returns {Promise<Array<{content: string, source: string, vecRank: number|null, bm25Rank: number|null, rrfScore: number}>>}
 *   Fused results with per-retriever ranks.
 */
export async function hybridSearchWithScores(query, k = 3) {
  if (!_vectorstore || !_documents) {
    throw new Error("No index found. Run indexDocuments() first.");
  }

  // Per-retriever candidate lists (top k*2 each). A chunk that one side
  // misses entirely is a "blind spot" — reported as a null rank.
  const vecResults = await _vectorstore.similaritySearch(query, k * 2);
  const vecChunks = vecResults.map((doc) => doc.pageContent);
  const bm25Chunks = _bm25Search(query, _documents, k * 2);

  const sources = {};
  for (const doc of _documents) {
    sources[doc.pageContent] = doc.metadata?.source || "unknown";
  }

  const rrfScores = {};

  vecChunks.forEach((chunk, i) => {
    const rank = i + 1;
    rrfScores[chunk] = (rrfScores[chunk] || 0) + 1.0 / (RRF_K + rank);
  });
  bm25Chunks.forEach((chunk, i) => {
    const rank = i + 1;
    rrfScores[chunk] = (rrfScores[chunk] || 0) + 1.0 / (RRF_K + rank);
  });

  return Object.entries(rrfScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, k)
    .map(([chunk, score]) => ({
      content: chunk,
      source: sources[chunk] || "unknown",
      vecRank: vecChunks.indexOf(chunk) + 1 || null,
      bm25Rank: bm25Chunks.indexOf(chunk) + 1 || null,
      rrfScore: score,
    }));
}

/**
 * Simple BM25-inspired keyword search.
 * Scores documents by term frequency of query words (lowercased, split on
 * non-alphanumerics so "INC-799" matches "inc" + "799").
 */
function _bm25Search(query, documents, k) {
  const queryTokens = _tokenize(query);
  const scored = documents.map((doc) => {
    const docTokens = _tokenize(doc.pageContent);
    let score = 0;
    for (const term of queryTokens) {
      score += docTokens.filter((t) => t === term).length;
    }
    return { text: doc.pageContent, score };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, k).map((s) => s.text);
}

/**
 * The "augment + generate" step: inject ALREADY-RETRIEVED chunks into a
 * system prompt and ask the LLM to answer. The system prompt is the
 * guardrail — pass SYSTEM_PROMPT to ground, or NO_GUARDRAIL_PROMPT to see
 * what the model does without it.
 *
 * Kept separate from retrieval so callers can inspect (and display) the
 * exact chunks that ground the answer before sending them to the model.
 *
 * @param {string} query - The user's question.
 * @param {string[]} chunks - Pre-retrieved chunk contents (from retrieve / hybridSearch).
 * @param {string} [systemPrompt=SYSTEM_PROMPT] - Prompt template (must contain a {context} slot).
 * @param {number} [temperature=0.0] - 0.0 for deterministic output.
 * @param {number} [maxTokens=500] - Max tokens in LLM response.
 * @returns {Promise<string>} The LLM's answer.
 */
export async function answerWithContext(
  query,
  chunks,
  systemPrompt = SYSTEM_PROMPT,
  temperature = 0.0,
  maxTokens = 500
) {
  const context = chunks.join("\n\n---\n\n");
  const llm = getLlm({ temperature, maxTokens });
  const response = await llm.invoke([
    new SystemMessage(systemPrompt.replace("{context}", context)),
    new HumanMessage(query),
  ]);
  return response.content.trim();
}

/**
 * Ground an answer using SYSTEM_PROMPT (the guardrail). See answerWithContext.
 *
 * @param {string} query - The user's question.
 * @param {string[]} chunks - Pre-retrieved chunk contents.
 * @param {number} [temperature=0.0] - 0.0 for deterministic output.
 * @param {number} [maxTokens=500] - Max tokens in LLM response.
 * @returns {Promise<string>} The LLM's answer.
 */
export async function groundedAnswerFromChunks(
  query,
  chunks,
  temperature = 0.0,
  maxTokens = 500
) {
  return answerWithContext(query, chunks, SYSTEM_PROMPT, temperature, maxTokens);
}

/**
 * Answer a question grounded in the retrieved context.
 *
 * Retrieves top-k chunks, injects them into the prompt, and asks the LLM
 * to answer strictly from the provided context.
 *
 * @param {string} query - The user's question.
 * @param {number} [k=3] - Number of chunks to retrieve.
 * @param {number} [temperature=0.0] - 0.0 for deterministic output.
 * @param {number} [maxTokens=500] - Max tokens in LLM response.
 * @returns {Promise<string>} The LLM's answer, grounded in retrieved documents.
 */
export async function groundedAnswer(query, k = 3, temperature = 0.0, maxTokens = 500) {
  const chunks = await retrieve(query, k);
  return groundedAnswerFromChunks(query, chunks, temperature, maxTokens);
}

/**
 * Same as groundedAnswer, but also returns the retrieved chunks
 * for transparency — engineers can verify the grounding.
 *
 * @param {string} query - The user's question.
 * @param {number} [k=3] - Number of chunks to retrieve.
 * @param {number} [temperature=0.0] - 0.0 for deterministic output.
 * @param {number} [maxTokens=500] - Max tokens in LLM response.
 * @returns {Promise<[string, string[]]>} Tuple of [answer, list_of_retrieved_chunks].
 */
export async function groundedAnswerWithChunks(
  query,
  k = 3,
  temperature = 0.0,
  maxTokens = 500
) {
  const chunks = await retrieve(query, k);
  const answer = await groundedAnswerFromChunks(query, chunks, temperature, maxTokens);
  return [answer, chunks];
}
