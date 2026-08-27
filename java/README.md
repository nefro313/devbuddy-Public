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
    │   │   └── cost/
    │   │       └── CostTracker.java        # Token → cost calculation
    │   └── resources/
    │       ├── application.properties      # API key + model config
    │       └── logback.xml                 # Clean console logging (%msg%n)
    └── test/
        └── java/devbuddy/
            └── IntegrationTest.java        # 5 smoke tests (JUnit 5)
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
