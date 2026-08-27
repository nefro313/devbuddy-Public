package devbuddy.rag;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.VectorParams;
import io.qdrant.client.grpc.Points.PointStruct;
import io.qdrant.client.grpc.Points.ScoredPoint;
import io.qdrant.client.grpc.Points.SearchPoints;
import io.qdrant.client.grpc.Points.WithPayloadSelector;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.openai.OpenAiChatOptions;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static io.qdrant.client.PointIdFactory.id;
import static io.qdrant.client.ValueFactory.value;
import static io.qdrant.client.VectorsFactory.vectors;

/**
 * Week 3 — RAG pipeline: embed, chunk, store, retrieve, ground.
 *
 * <p>Equivalent to {@code src/rag.py} / {@code src/rag.js}. Qdrant (Docker,
 * gRPC port 6334) is the vector store; embeddings are the local
 * {@code all-MiniLM-L6-v2} model; hybrid search fuses vector + BM25 via
 * Reciprocal Rank Fusion (RRF).</p>
 *
 * <p>Import graph: {@code rag → llm → config} (ChatClient is wired in
 * {@code AppConfig}).</p>
 */
public class RagService implements AutoCloseable {

    /** Collection name — must match Python/Node.js ({@code devbuddy-docs}). */
    public static final String COLLECTION = "devbuddy-docs";

    private static final Path DEFAULT_DATA_DIR = Path.of("..", "shared", "data");

    private static final java.util.regex.Pattern TOKEN_PATTERN =
            java.util.regex.Pattern.compile("[a-z0-9]+");

    /** Display name of the embedding model (384-dim), matching Python/Node.js. */
    public static final String EMBEDDING_MODEL = "all-MiniLM-L6-v2";

    /** RRF fusion constant — single source of truth (demo-04 references this). */
    public static final double RRF_K = 60.0;

    /**
     * The system prompt is the guardrail: constrain the model to the context
     * and make it decline out-of-corpus questions. Contains a {@code %s} slot.
     */
    public static final String SYSTEM_PROMPT = """
            You are a knowledge base assistant. Answer the user's question using ONLY the provided context below. If the context does not contain the answer, say 'I don't have information about that in my knowledge base.' Never invent information.

            CONTEXT:
            %s""";

    /**
     * The SAME prompt with the guardrail removed — used to show what happens
     * without it (the model is no longer told to decline).
     */
    public static final String NO_GUARDRAIL_PROMPT = """
            You are a helpful assistant. Answer the user's question, even if you have to make reasonable assumptions. Be specific.

            CONTEXT:
            %s""";

    private final ChatClient chatClient;
    private final String model;
    private final EmbeddingService embeddings;
    private final String qdrantHost;
    private final int qdrantGrpcPort;

    private List<Chunk> documents = List.of();
    private boolean indexed = false;

    public RagService(ChatClient chatClient, String model, EmbeddingService embeddings,
                      String qdrantHost, int qdrantGrpcPort) {
        this.chatClient = chatClient;
        this.model = model;
        this.embeddings = embeddings;
        this.qdrantHost = qdrantHost;
        this.qdrantGrpcPort = qdrantGrpcPort;
    }

    /** Answer plus the retrieved chunks that grounded it (for transparency). */
    public record GroundedResult(String answer, List<String> chunks) {}

    /** A retrieved chunk together with its source document and similarity score. */
    public record RetrievedChunk(String content, String source, double score) {}

    /**
     * A hybrid-search hit with its per-retriever ranks — makes RRF visible.
     * vecRank / bm25Rank are 1-based ranks in each retriever's candidate list
     * (top k*2); null means that retriever never ranked the chunk (a blind
     * spot). rrfScore is the fused score, the sum of 1/(RRF_K + rank) over both.
     */
    public record HybridResult(String content, String source,
                               Integer vecRank, Integer bm25Rank, double rrfScore) {}

    // ─── Index ────────────────────────────────────────────────

    public int indexDocuments() {
        return indexDocuments(null, 512, 64);
    }

    /**
     * Load {@code .md}/{@code .txt} files, chunk, embed, and store in Qdrant.
     * The collection is recreated from scratch on every call.
     *
     * @return number of chunks indexed
     */
    public int indexDocuments(String directory, int chunkSize, int chunkOverlap) {
        Path target = directory == null || directory.isBlank() ? DEFAULT_DATA_DIR : Path.of(directory);
        try {
            List<Chunk> chunks = DocumentChunker.loadAndSplit(target, chunkSize, chunkOverlap);
            // Drop heading-only chunks: they rank high on similarity but carry
            // no answer content (a bare "# Title" + date/owner metadata).
            chunks = chunks.stream().filter(c -> !isTitleOnly(c.content())).toList();
            int dimension = embeddings.dimension();

            try (QdrantClient client = newClient()) {
                deleteCollectionQuietly(client);

                client.createCollectionAsync(COLLECTION,
                                VectorParams.newBuilder()
                                        .setDistance(Distance.Cosine)
                                        .setSize(dimension)
                                        .build())
                        .get(30, TimeUnit.SECONDS);

                List<PointStruct> points = new ArrayList<>(chunks.size());
                for (Chunk chunk : chunks) {
                    points.add(PointStruct.newBuilder()
                            .setId(id(UUID.randomUUID()))
                            .setVectors(vectors(embeddings.embed(chunk.content())))
                            .putPayload("text", value(chunk.content()))
                            .putPayload("source", value(chunk.source()))
                            .build());
                }
                client.upsertAsync(COLLECTION, points).get(120, TimeUnit.SECONDS);
            }

            this.documents = chunks;
            this.indexed = true;
            return chunks.size();
        } catch (Exception e) {
            throw new RuntimeException("Failed to index documents from " + target + ": " + e.getMessage(), e);
        }
    }

    // ─── Retrieve ─────────────────────────────────────────────

    public List<String> retrieve(String query) {
        return retrieve(query, 3);
    }

    /**
     * Top-k semantic search over the indexed chunks.
     */
    public List<String> retrieve(String query, int k) {
        return retrieveWithSources(query, k).stream().map(RetrievedChunk::content).toList();
    }

    /**
     * Top-k semantic search together with each chunk's source document.
     */
    public List<RetrievedChunk> retrieveWithSources(String query, int k) {
        return retrieveWithSources(query, k, null);
    }

    /**
     * Top-k semantic search together with source and cosine similarity score.
     * An optional {@code minScore} cutoff turns "best guess" into "no match".
     */
    public List<RetrievedChunk> retrieveWithSources(String query, int k, Double minScore) {
        requireIndexed();
        try (QdrantClient client = newClient()) {
            List<ScoredPoint> results = client.searchAsync(SearchPoints.newBuilder()
                            .setCollectionName(COLLECTION)
                            .addAllVector(toFloatList(embeddings.embed(query)))
                            .setLimit(k)
                            .setWithPayload(WithPayloadSelector.newBuilder().setEnable(true).build())
                            .build())
                    .get(30, TimeUnit.SECONDS);

            List<RetrievedChunk> out = new ArrayList<>(results.size());
            for (ScoredPoint point : results) {
                float score = point.getScore();
                if (minScore != null && score < minScore) {
                    continue;
                }
                var payload = point.getPayloadMap();
                if (payload != null && payload.containsKey("text")) {
                    out.add(new RetrievedChunk(
                            payload.get("text").getStringValue(),
                            payload.containsKey("source") ? payload.get("source").getStringValue() : "unknown",
                            score));
                }
            }
            return out;
        } catch (Exception e) {
            throw new RuntimeException("Retrieval failed: " + e.getMessage(), e);
        }
    }

    /** Embed a single piece of text into a vector (for inspection / demos). */
    public float[] embedText(String text) {
        return embeddings.embed(text);
    }

    // ─── Hybrid search ────────────────────────────────────────

    public List<String> hybridSearch(String query) {
        return hybridSearch(query, 3);
    }

    /**
     * Vector (semantic) + BM25 (keyword) fused via Reciprocal Rank Fusion.
     */
    public List<String> hybridSearch(String query, int k) {
        return hybridSearchWithScores(query, k).stream().map(HybridResult::content).toList();
    }

    /**
     * hybridSearch() plus the internals: for every final hit, report its rank
     * in EACH retriever (null = that retriever never ranked it) and the fused
     * RRF score. RRF: score = sum of 1/(RRF_K + rank) over both rankings.
     */
    public List<HybridResult> hybridSearchWithScores(String query, int k) {
        requireIndexed();
        List<RetrievedChunk> vectorChunks = retrieveWithSources(query, k * 2);
        List<RetrievedChunk> bm25Chunks = bm25(query, k * 2);

        Map<String, Double> scores = new HashMap<>();
        for (int i = 0; i < vectorChunks.size(); i++) {
            scores.merge(vectorChunks.get(i).content(), 1.0 / (RRF_K + i + 1), Double::sum);
        }
        for (int i = 0; i < bm25Chunks.size(); i++) {
            scores.merge(bm25Chunks.get(i).content(), 1.0 / (RRF_K + i + 1), Double::sum);
        }

        Map<String, String> sources = new HashMap<>();
        for (RetrievedChunk c : vectorChunks) sources.put(c.content(), c.source());
        for (RetrievedChunk c : bm25Chunks) sources.put(c.content(), c.source());

        return scores.entrySet().stream()
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .limit(k)
                .map(e -> new HybridResult(
                        e.getKey(),
                        sources.getOrDefault(e.getKey(), "unknown"),
                        rankOf(vectorChunks, e.getKey()),
                        rankOf(bm25Chunks, e.getKey()),
                        e.getValue()))
                .toList();
    }

    /** 1-based rank of content in the list, or null if absent (a blind spot). */
    private static Integer rankOf(List<RetrievedChunk> list, String content) {
        for (int i = 0; i < list.size(); i++) {
            if (list.get(i).content().equals(content)) {
                return i + 1;
            }
        }
        return null;
    }

    /** True if a chunk is only a heading + blockquote metadata (no body). */
    private static boolean isTitleOnly(String text) {
        int wordCount = 0;
        for (String line : text.split("\n")) {
            String stripped = line.strip();
            if (stripped.isEmpty() || stripped.startsWith("#") || stripped.startsWith(">")) {
                continue;
            }
            wordCount += stripped.split("\\s+").length;
        }
        return wordCount < 8;
    }

    /** Simple in-memory BM25-style keyword scoring (mirrors Node.js). */
    private List<RetrievedChunk> bm25(String query, int k) {
        List<String> queryTokens = tokenize(query);
        record Scored(RetrievedChunk chunk, int score) {}

        List<Scored> scored = new ArrayList<>(documents.size());
        for (Chunk doc : documents) {
            List<String> docTokens = tokenize(doc.content());
            int score = 0;
            for (String term : queryTokens) {
                score += (int) docTokens.stream().filter(term::equals).count();
            }
            if (score > 0) {
                scored.add(new Scored(new RetrievedChunk(doc.content(), doc.source(), 0.0), score));
            }
        }

        return scored.stream()
                .sorted(Comparator.comparingInt(Scored::score).reversed())
                .limit(k)
                .map(Scored::chunk)
                .toList();
    }

    /** Lowercase and split on non-alphanumerics so "INC-799" matches "inc" + "799". */
    private static List<String> tokenize(String text) {
        List<String> tokens = new ArrayList<>();
        var matcher = TOKEN_PATTERN.matcher(text.toLowerCase());
        while (matcher.find()) {
            tokens.add(matcher.group());
        }
        return tokens;
    }

    // ─── Grounded answers ─────────────────────────────────────

    /**
     * Retrieve top-k chunks, inject them into the system prompt, and ask the
     * LLM to answer strictly from that context.
     */
    public String groundedAnswer(String query, int k, double temperature) {
        List<String> chunks = retrieve(query, k);
        return groundedAnswerFromChunks(query, chunks, temperature);
    }

    /**
     * Same as {@link #groundedAnswer}, but also returns the retrieved chunks.
     */
    public GroundedResult groundedAnswerWithChunks(String query, int k, double temperature) {
        List<String> chunks = retrieve(query, k);
        return new GroundedResult(groundedAnswerFromChunks(query, chunks, temperature), chunks);
    }

    /**
     * Ground an answer using {@link #SYSTEM_PROMPT} (the guardrail).
     * See {@link #answerWithContext}.
     */
    public String groundedAnswerFromChunks(String query, List<String> chunks, double temperature) {
        return answerWithContext(query, chunks, SYSTEM_PROMPT, temperature);
    }

    /**
     * The "augment + generate" step: inject ALREADY-RETRIEVED chunks into a
     * system prompt and ask the LLM to answer. The system prompt is the
     * guardrail — pass {@link #SYSTEM_PROMPT} to ground, or
     * {@link #NO_GUARDRAIL_PROMPT} to see what the model does without it.
     * Kept separate from retrieval so callers can inspect (and display) the
     * exact chunks that ground the answer before sending them to the model.
     */
    public String answerWithContext(String query, List<String> chunks,
                                    String systemPrompt, double temperature) {
        if (chatClient == null) {
            throw new IllegalStateException("ChatClient is not configured — grounded answers need the LLM.");
        }
        String context = String.join("\n\n---\n\n", chunks);
        var response = chatClient.prompt()
                .system(systemPrompt.formatted(context))
                .user(query)
                .options(OpenAiChatOptions.builder()
                        .model(model)
                        .temperature(temperature)
                        .build())
                .call()
                .chatResponse();
        return response.getResult().getOutput().getText().strip();
    }

    // ─── Qdrant plumbing ──────────────────────────────────────

    private void requireIndexed() {
        if (!indexed) {
            throw new IllegalStateException("No index found. Run indexDocuments() first.");
        }
    }

    private QdrantClient newClient() {
        return new QdrantClient(QdrantGrpcClient.newBuilder(qdrantHost, qdrantGrpcPort, false).build());
    }

    private void deleteCollectionQuietly(QdrantClient client) {
        try {
            client.deleteCollectionAsync(COLLECTION).get(10, TimeUnit.SECONDS);
        } catch (Exception ignored) {
            // Collection does not exist yet — fine on first run.
        }
    }

    private static List<Float> toFloatList(float[] array) {
        List<Float> out = new ArrayList<>(array.length);
        for (float value : array) {
            out.add(value);
        }
        return out;
    }

    @Override
    public void close() {
        embeddings.close();
    }
}
