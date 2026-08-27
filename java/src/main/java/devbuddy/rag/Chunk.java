package devbuddy.rag;

/**
 * A single chunk of document text plus its source file name.
 *
 * <p>Equivalent to LangChain's {@code Document(page_content, metadata)}
 * in Python/Node.js, reduced to the two fields the RAG pipeline needs.</p>
 */
public record Chunk(String content, String source) {

    public Chunk {
        content = content == null ? "" : content;
        source = source == null ? "" : source;
    }
}
