package devbuddy.rag;

import ai.djl.huggingface.tokenizers.HuggingFaceTokenizer;
import ai.djl.huggingface.translator.TextEmbeddingTranslator;
import ai.djl.inference.Predictor;
import ai.djl.ndarray.NDManager;
import ai.djl.repository.zoo.Criteria;
import ai.djl.repository.zoo.ZooModel;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Week 3 — local sentence-transformer embeddings via DJL + ONNX Runtime.
 *
 * <p>Loads {@code all-MiniLM-L6-v2} (384-dim) exactly like Python's
 * {@code HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")} and Node.js's
 * {@code @xenova/transformers} — local, free, no API cost. The ONNX model and
 * tokenizer are downloaded once from Hugging Face on first use (~80MB), then
 * cached under {@code ~/.cache/devbuddy/embeddings/all-MiniLM-L6-v2}.</p>
 */
public class EmbeddingService implements AutoCloseable {

    private static final String HF_BASE =
            "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/";

    private final Path modelDir;
    private ZooModel<String, float[]> model;
    private Predictor<String, float[]> predictor;

    public EmbeddingService() {
        this(defaultModelDir());
    }

    public EmbeddingService(Path modelDir) {
        this.modelDir = modelDir;
    }

    private static Path defaultModelDir() {
        String home = System.getProperty("user.home", ".");
        return Path.of(home, ".cache", "devbuddy", "embeddings", "all-MiniLM-L6-v2");
    }

    /**
     * Embed a single piece of text into a normalized 384-dim vector.
     */
    public synchronized float[] embed(String text) {
        ensureLoaded();
        try {
            return predictor.predict(text);
        } catch (Exception e) {
            throw new RuntimeException("Embedding failed: " + e.getMessage(), e);
        }
    }

    /** Embedding vector size (384 for all-MiniLM-L6-v2). */
    public synchronized int dimension() {
        return embed("dimension probe").length;
    }

    private void ensureLoaded() {
        if (predictor != null) {
            return;
        }
        try {
            downloadIfMissing();

            // One base manager per service instance; the tokenizer keeps it alive.
            NDManager manager = NDManager.newBaseManager();

            HuggingFaceTokenizer tokenizer = HuggingFaceTokenizer.builder()
                    .optTokenizerPath(modelDir.resolve("tokenizer.json"))
                    .optManager(manager)
                    .build();

            // sentence-transformers defaults: mean pooling + L2 normalize.
            // BERT-based models (incl. MiniLM) take input_ids + attention_mask
            // + token_type_ids, so include token types explicitly.
            TextEmbeddingTranslator translator = TextEmbeddingTranslator.builder(tokenizer)
                    .optPoolingMode("mean")
                    .optNormalize(true)
                    .optIncludeTokenTypes(true)
                    .build();

            Criteria<String, float[]> criteria = Criteria.builder()
                    .setTypes(String.class, float[].class)
                    .optModelPath(modelDir)
                    .optEngine("OnnxRuntime")
                    .optTranslator(translator)
                    .build();

            model = criteria.loadModel();
            predictor = model.newPredictor();
        } catch (Exception e) {
            throw new RuntimeException("Failed to load embedding model: " + e.getMessage(), e);
        }
    }

    private void downloadIfMissing() throws IOException, InterruptedException {
        Files.createDirectories(modelDir);
        download(HF_BASE + "onnx/model.onnx", modelDir.resolve("model.onnx"));
        download(HF_BASE + "tokenizer.json", modelDir.resolve("tokenizer.json"));
    }

    private void download(String url, Path destination) throws IOException, InterruptedException {
        if (Files.exists(destination) && Files.size(destination) > 0) {
            return;
        }
        HttpClient client = HttpClient.newBuilder()
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
        HttpRequest request = HttpRequest.newBuilder(URI.create(url)).GET().build();
        HttpResponse<Path> response = client.send(request, HttpResponse.BodyHandlers.ofFile(destination));
        if (response.statusCode() != 200) {
            throw new IOException("Failed to download " + url + " (HTTP " + response.statusCode() + ")");
        }
    }

    @Override
    public synchronized void close() {
        if (predictor != null) {
            predictor.close();
            predictor = null;
        }
        if (model != null) {
            model.close();
            model = null;
        }
    }
}
