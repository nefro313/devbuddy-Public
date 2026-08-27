# DevBuddy — Java CLI

> **Language Shepherd:** [TBD]
> **Blueprint Ready:** Week 0 | **Engineers can use from:** Week 0

## Quick Start

```bash
cd java

# Edit application.properties → set your OpenRouter API key
# openrouter.api.key=sk-or-your-key-here

# Build + run
mvn package -DskipTests -q
java -jar target/devbuddy-0.1.0.jar

# Or run tests
mvn test
```

Output:

```
============================================================
  DevBuddy Verification — Week 0 (Java)
============================================================

[1/3] Checking: auth-service...
  Status:      passing
  Confidence:  30%
  Reason:      I don't have real CI access...
  Tokens:      147 (102 in / 45 out)
  Cost:        $0.000042
  Time:        1.23s
  Type:        BuildCheck ← typed record, not a string!

============================================================
  ✅ VERIFICATION PASSED
  Java:       21.0.1
  Model:      openai/gpt-4o-mini
  Total tokens: 441
  Total cost:   $0.000126
============================================================
```

## Stack

| Layer | Choice |
|-------|--------|
| LLM Provider | OpenRouter (via Spring AI `spring-ai-openai`) |
| DI Container | Spring Framework `AnnotationConfigApplicationContext` |
| Validation / Structured Output | Java records + Jackson + native `response_format=json_schema` |
| Vector Store (Week 3) | Qdrant (Docker, gRPC `io.qdrant:client`) |
| Embeddings (Week 3) | `all-MiniLM-L6-v2` (local, DJL + ONNX Runtime, no API cost) |
| Build Tool | Maven (no Boot, no embedded server) |

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Verification.main()                             │
│    │                                              │
│    ├─ new AnnotationConfigApplicationContext(AppConfig)  │
│    │     │                                        │
│    │     ├─ @Bean OpenAiApi     ← application.properties   │
│    │     ├─ @Bean ChatModel     ← OpenRouter base URL  │
│    │     └─ @Bean ChatClient    ← wraps ChatModel      │
│    │                                              │
│    ├─ chatClient.prompt().call().chatResponse()   │
│    │     │                                        │
│    │     ├─ → OpenRouter → model response         │
│    │     ├─ Jackson parse → BuildCheck record     │
│    │     ├─ Usage metadata → CostTracker.cost()   │
│    │     └─ log.info(...) per-call report         │
│    │                                              │
│    └─ Summary: tokens, cost, ✓ PASSED             │
└──────────────────────────────────────────────────┘
```

No Spring Boot. No embedded web server. Just Spring IoC + Spring AI.

## Project Structure

```
java/
├── pom.xml
├── README.md
└── src/
    ├── main/
    │   ├── java/devbuddy/
    │   │   ├── Verification.java           # Entry point + verification loop
    │   │   ├── config/
    │   │   │   └── AppConfig.java          # @Configuration — wires OpenAiApi, ChatModel, ChatClient
│   │   ├── schemas/
    │   │   │   ├── BuildCheck.java         # Typed record (Jackson serialization)
    │   │   │   ├── JsonSchemas.java        # JSON schemas → response_format=json_schema
    │   │   │   └── SchemasService.java     # analyzePr + generateReadinessReport (Week 2)
    │   │   ├── scripts/week02/            # Week 2 demos (run with mvn exec:java)
    │   │   ├── scripts/week03/            # Week 3 RAG demos (embed/retrieve/ground, hybrid)
    │   │   ├── rag/                       # Week 3 RAG pipeline
    │   │   │   ├── RagService.java        # index/retrieve/hybridSearch/groundedAnswer
    │   │   │   ├── EmbeddingService.java  # all-MiniLM-L6-v2 via DJL + ONNX Runtime
    │   │   │   └── DocumentChunker.java   # recursive character splitter
    │   │   └── cost/
    │   │       └── CostTracker.java        # Token → cost calculation
    │   └── resources/
    │       ├── application.properties      # API key + model config
    │       └── logback.xml                 # Clean console logging (%msg%n)
    └── test/
        └── java/devbuddy/
            ├── IntegrationTest.java        # 5 smoke tests (JUnit 5)
            ├── RagTest.java                # Week 3 RAG (retrieval — needs Qdrant)
            └── RagLlmTest.java             # Week 3 grounded answers (needs OpenRouter)
```

## Differences from Python / Node.js

| Concept | Python | Node.js | Java |
|---------|--------|---------|------|
| LLM Client | `ChatOpenAI(...)` | `new ChatOpenAI({...})` | `OpenAiApi.builder()` + `OpenAiChatModel.builder()` |
| DI | None (module imports) | None (module imports) | `@Configuration` + `@Bean` → `AnnotationConfigApplicationContext` |
| Config | `load_dotenv()` | `dotenv.config()` | `application.properties` + `@PropertySource` |
| Structured output | `with_structured_output()` | `withStructuredOutput()` | `response_format=json_schema` (native) → Jackson parse + record validation |
| Cost tracking | Inline in verification | `config.js` export | `CostTracker` static utility |
| Entry point | `if __name__ == "__main__"` | `main().catch(...)` | `Verification.main()` bootstraps Spring context |
| Embeddings | `HuggingFaceEmbeddings` | `@xenova/transformers` | DJL + ONNX Runtime (`EmbeddingService`) |
| Vector store | `QdrantVectorStore` (REST 6333) | `@langchain/qdrant` (REST 6333) | `QdrantClient` (gRPC 6334) |

## Week 2 — Structured Output Demos

Week 2 introduces native structured output (`response_format=json_schema`) — the
Java equivalent of `with_structured_output()` / `withStructuredOutput()`. The
schemas live in `JsonSchemas.java` and are enforced at the API level.

> **Why not `ChatClient.entity()`?** Spring AI's `.entity(Class)` (via
> `BeanOutputConverter`) embeds the JSON schema in the prompt and parses the
> reply — a "polite request", not a token-level constraint. That is true even in
> 1.0.0 GA (verified against the `ChatModelCallAdvisor` bytecode, which appends
> the schema to the user message). Native `response_format=json_schema` is what
> makes the model *unable* to return output that violates the schema, so that is
> what this blueprint uses.

```bash
cd java

# Demo 2: raw JSON prompting vs. native structured output
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo02RawVsStructured

# Demo 3: inference parameters (temperature + max_tokens)
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo03InferenceParameters

# Explore: validate a ServiceReadinessReport from shared/data (no API calls)
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.ExploreReadinessReport
```

## Week 3 — RAG & Context Engineering

Week 3 grounds the model in your own data: embed, chunk, store in Qdrant,
retrieve, then answer strictly from the retrieved context. Mirrors
`src/rag.py` / `src/rag.js`.

**Prerequisites:** Qdrant running (`docker-compose up -d` from the repo root),
plus `OPENROUTER_API_KEY` for the grounded-answer demos. The embedding model
(`all-MiniLM-L6-v2`, ~24MB) downloads once on first use.

```bash
cd java

# Demo 1: embed → retrieve → ground (needs OPENROUTER_API_KEY)
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo01EmbedRetrieveGround

# Demo 2: out-of-corpus vs in-corpus (needs OPENROUTER_API_KEY)
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo02HallucinateGround

# Demo 3: chunk size 256/512/1024 (no API key — Qdrant only)
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo03ChunkSize

# Demo 4: hybrid search, vector + BM25 + RRF (no API key)
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo04HybridSearch

# Tests (retrieval only — needs Qdrant)
mvn test -Dtest=RagTest

# Tests (grounded answers — needs Qdrant + OPENROUTER_API_KEY)
mvn test -Dtest=RagLlmTest
```

| Function | What it does |
|----------|--------------|
| `indexDocuments(dir, chunkSize, chunkOverlap)` | Load `.md`/`.txt`, chunk, embed, store in Qdrant |
| `retrieve(query, k)` | Top-k semantic search |
| `hybridSearch(query, k)` | BM25 + vector fused via Reciprocal Rank Fusion |
| `groundedAnswer(query, k, temperature)` | Retrieve → inject context → LLM answer |
| `groundedAnswerWithChunks(query, k, temperature)` | Answer + retrieved chunks for transparency |

> **Why Qdrant, not Chroma?** Qdrant is production-grade, cross-language
> (Python/Node/Java all hit the same `devbuddy-docs` collection), and ships a
> dashboard at http://localhost:6333/dashboard. The Java client uses gRPC
> (port 6334); Python/Node use the REST API (port 6333).

## Each Week

```bash
cd java

# Pull latest from upstream
git pull upstream main

# Read the task
cat ../docs/week-NN.md

# Build in src/main/java/devbuddy/
# Run:
mvn package -DskipTests -q && java -jar target/devbuddy-0.1.0.jar
```
