# DevBuddy — Setup Guide (Java)

This is the current working setup for the Java project in this repo.

---

## Prerequisites

- Java JDK (not JRE-only, `javac` must be available)
- Maven
- Git
- An OpenRouter API key

> For the Week 2 demos, use `openai/gpt-4o-mini` as the model. Free models may be used for a smoke check, but they are not reliable for structured-output demos in Java.

---

## 1) Confirm you are in the repo

```bash
cd /path/to/devbuddy
git checkout week-02
git status
```

Windows PowerShell:

```powershell
cd C:\path\to\devbuddy
git checkout week-02
git status
```

---

## 2) Check your Java toolchain

```bash
java -version
javac -version
mvn -version
```

If `javac` is missing or Maven reports `release version ... not supported`, install/activate a full JDK and verify both `java` and `javac` are from the same installation.

---

## 3) Configure the environment

```bash
cd java
cp src/main/resources/application.properties.example src/main/resources/application.properties
```

Windows PowerShell:

```powershell
cd java
Copy-Item src/main/resources/application.properties.example src/main/resources/application.properties
```

Then edit the file and set:

```properties
openrouter.api.key=sk-or-your-key
devbuddy.model=openai/gpt-4o-mini
```

The repo’s current Java configuration expects `application.properties` to exist in `src/main/resources/`.

---

## 4) Build the project

```bash
cd java
mvn package -DskipTests -q
```

---

## 5) Run the verification script

```bash
cd java
java -jar target/devbuddy-0.1.0.jar
```

---

## 6) Run the Week 2 demos

```bash
cd java
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo01ProseVsStructured
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo02RawVsStructured
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo03InferenceParameters
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo04Sketchpad
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo05AgenticRetry
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo06PromptEngineering
mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.ExploreReadinessReport
```

---

## 7) Run schema-only tests

```bash
cd java
mvn test -Dtest=SchemasTest
```

---

## Troubleshooting

### `Source option ... is no longer supported`

This means the active JDK is too old for the Maven compiler release in the repo.

### `release version ... not supported`

This usually means Java runtime exists but the compiler (`javac`) is missing or on a different version.

Check:

```bash
javac -version
```

If missing, install a full JDK and re-check both `java` and `javac` versions.

### `openrouter.api.key is not set`

Check `src/main/resources/application.properties` and confirm the key is present.

### `JSON schema / function calling` issues

Use:

```properties
devbuddy.model=openai/gpt-4o-mini
```

Do not use a free model for the main Week 2 demo flow.

---

## Verified status in this environment

We ran:

```bash
cd /home/nabarup_maity/devbuddy/java && mvn -q -DskipTests compile
```

and it failed with:

- `Fatal error compiling: error: release version ... not supported`
- `javac: command not found`

This is a Java toolchain mismatch, not a repo logic error. The project requires a full JDK
for the current Maven configuration.
