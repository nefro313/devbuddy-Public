package devbuddy.rag;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.List;
import java.util.stream.Stream;

/**
 * Week 3 — loads {@code .md}/{@code .txt} files and splits them into chunks.
 *
 * <p>Mirrors LangChain's {@code RecursiveCharacterTextSplitter} (used by the
 * Python/Node implementations) with the same separator priority order:</p>
 *
 * <pre>{@code
 * ["\n# ", "\n## ", "\n### ", "\n#### ", "\n", " ", ""]
 * }</pre>
 *
 * <p>Two properties matter for retrieval quality and are preserved here:</p>
 * <ol>
 *   <li><b>Separators are kept</b> — each separator is re-attached to the
 *       following piece, so headings ({@code ## Title}) and newlines survive
 *       and chunks start on a heading or word, not mid-sentence.</li>
 *   <li><b>Word boundaries are never split</b> — chunks and overlap are built
 *       from whole pieces, so a word like {@code "Lint"} is never cut into
 *       {@code "L"} + {@code "int"}.</li>
 * </ol>
 */
public final class DocumentChunker {

    private static final String[] SEPARATORS = {
            "\n# ", "\n## ", "\n### ", "\n#### ", "\n", " ", ""
    };

    private DocumentChunker() {
        // utility class
    }

    /**
     * Load every {@code .md} and {@code .txt} file under {@code directory}
     * (recursively) and split each into chunks.
     */
    public static List<Chunk> loadAndSplit(Path directory, int chunkSize, int chunkOverlap) throws IOException {
        List<Path> files = listFiles(directory);
        if (files.isEmpty()) {
            throw new IOException("No .md or .txt files found in " + directory);
        }
        List<Chunk> chunks = new ArrayList<>();
        for (Path file : files) {
            String content = Files.readString(file);
            chunks.addAll(split(content, file.getFileName().toString(), chunkSize, chunkOverlap));
        }
        return chunks;
    }

    /**
     * Split a single document's content into chunks.
     */
    public static List<Chunk> split(String content, String source, int chunkSize, int chunkOverlap) {
        List<String> pieces = splitPieces(content, SEPARATORS, chunkSize);
        List<String> merged = merge(pieces, chunkSize, chunkOverlap);
        List<Chunk> chunks = new ArrayList<>(merged.size());
        for (String text : merged) {
            chunks.add(new Chunk(text, source));
        }
        return chunks;
    }

    private static List<Path> listFiles(Path directory) throws IOException {
        if (!Files.isDirectory(directory)) {
            throw new IOException("Not a directory: " + directory);
        }
        try (Stream<Path> walk = Files.walk(directory)) {
            return walk
                    .filter(Files::isRegularFile)
                    .filter(DocumentChunker::isMarkdownOrText)
                    .sorted()
                    .toList();
        }
    }

    private static boolean isMarkdownOrText(Path path) {
        String name = path.getFileName().toString().toLowerCase();
        return name.endsWith(".md") || name.endsWith(".txt");
    }

    /**
     * Recursively split on each separator (in priority order) until every piece
     * fits within {@code chunkSize}. The final {@code ""} separator hard-splits.
     */
    private static List<String> splitPieces(String text, String[] separators, int chunkSize) {
        String separator = separators[0];

        if (separator.isEmpty()) {
            return hardSplit(text, chunkSize);
        }

        String[] rest = separators.length > 1
                ? Arrays.copyOfRange(separators, 1, separators.length)
                : new String[0];

        List<String> out = new ArrayList<>();
        for (String piece : splitKeeping(text, separator)) {
            if (piece.isEmpty()) {
                continue;
            }
            if (piece.length() <= chunkSize) {
                out.add(piece);
            } else if (rest.length > 0) {
                out.addAll(splitPieces(piece, rest, chunkSize));
            } else {
                out.addAll(hardSplit(piece, chunkSize));
            }
        }
        return out;
    }

    /**
     * Split on {@code separator}, keeping it attached to the front of each
     * following piece. {@code "a\n# b"} on {@code "\n# "} → {@code ["a", "\n# b"]}.
     */
    private static List<String> splitKeeping(String text, String separator) {
        List<String> out = new ArrayList<>();
        int start = 0;
        int idx = text.indexOf(separator);
        while (idx >= 0) {
            if (idx > start) {
                out.add(text.substring(start, idx));
            }
            int next = text.indexOf(separator, idx + separator.length());
            int end = next >= 0 ? next : text.length();
            out.add(text.substring(idx, end));
            start = end;
            idx = next;
        }
        if (start < text.length()) {
            out.add(text.substring(start));
        }
        return out;
    }

    private static List<String> hardSplit(String text, int chunkSize) {
        List<String> out = new ArrayList<>();
        for (int i = 0; i < text.length(); i += chunkSize) {
            out.add(text.substring(i, Math.min(text.length(), i + chunkSize)));
        }
        return out;
    }

    /**
     * Merge pieces into chunks of at most {@code chunkSize} chars, never
     * cutting a piece in half (pieces are separator-delimited words/lines).
     * Overlap drops whole leading pieces until the remainder fits within
     * {@code chunkOverlap} — the LangChain overlap strategy.
     */
    private static List<String> merge(List<String> pieces, int chunkSize, int chunkOverlap) {
        List<String> chunks = new ArrayList<>();
        Deque<String> current = new ArrayDeque<>();
        int len = 0;

        for (String piece : pieces) {
            if (current.isEmpty() || len + piece.length() <= chunkSize) {
                current.addLast(piece);
                len += piece.length();
            } else {
                chunks.add(String.join("", current));
                // LangChain overlap trim: drop whole leading pieces until the
                // remainder fits within chunkOverlap AND the incoming piece fits.
                while (!current.isEmpty() && (len > chunkOverlap || len + piece.length() > chunkSize)) {
                    len -= current.removeFirst().length();
                }
                current.addLast(piece);
                len += piece.length();
            }
        }

        if (!current.isEmpty()) {
            chunks.add(String.join("", current));
        }
        return chunks;
    }
}
