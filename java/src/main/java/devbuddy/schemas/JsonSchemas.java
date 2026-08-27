package devbuddy.schemas;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.ai.openai.api.ResponseFormat;

import java.util.Map;

/**
 * Week 2 — JSON Schemas for native structured output.
 *
 * <p>These schemas are the <em>contract</em> the LLM is constrained to obey.
 * They are written in snake_case to match {@code shared/data/*.json}, the
 * Pydantic models in Python, and the Zod schemas in Node.js.</p>
 *
 * <p>They are passed to OpenAI's {@code response_format: json_schema} (strict
 * mode) so the model <em>cannot</em> return output that violates the schema —
 * the Java equivalent of Python's {@code with_structured_output()} and
 * Node.js's {@code withStructuredOutput()}.</p>
 */
public final class JsonSchemas {

    /** BuildCheck — flat, 4-field PR analysis (in-session exercise). */
    public static final String BUILD_CHECK = """
            {
              "type": "object",
              "properties": {
                "project": { "type": "string", "description": "Project or service name" },
                "severity": {
                  "type": "string",
                  "description": "How urgent is this change?",
                  "enum": ["low", "medium", "high", "critical"]
                },
                "summary": { "type": "string", "description": "One-sentence summary of the change" },
                "affected_files": {
                  "type": "array",
                  "description": "Files modified by this change",
                  "items": { "type": "string" }
                }
              },
              "required": ["project", "severity", "summary", "affected_files"],
              "additionalProperties": false
            }""";

    /** ServiceReadinessReport — composed, nested schema (self-learning + capstone preview). */
    public static final String SERVICE_READINESS_REPORT = """
            {
              "type": "object",
              "properties": {
                "service": {
                  "type": "object",
                  "properties": {
                    "name": { "type": "string", "description": "Service name, e.g. 'auth-service'" },
                    "version": { "type": "string", "description": "Currently deployed version, e.g. '2.1.0'" },
                    "owner_team": { "type": "string", "description": "Team responsible for this service" }
                  },
                  "required": ["name", "version", "owner_team"],
                  "additionalProperties": false
                },
                "build": {
                  "type": "object",
                  "properties": {
                    "status": {
                      "type": "string",
                      "description": "Current build/health status",
                      "enum": ["healthy", "degraded", "down", "unknown"]
                    },
                    "last_deploy": { "type": "string", "description": "ISO timestamp of the most recent deployment" },
                    "failing_since": { "type": ["string", "null"], "description": "ISO timestamp of when the build started failing, if degraded or down" }
                  },
                  "required": ["status", "last_deploy", "failing_since"],
                  "additionalProperties": false
                },
                "deployment": {
                  "type": "object",
                  "properties": {
                    "recent_deploys": {
                      "type": "array",
                      "description": "Last N deployments, most recent first",
                      "items": {
                        "type": "object",
                        "properties": {
                          "sha": { "type": "string", "description": "Commit SHA of the deployment" },
                          "author": { "type": "string", "description": "Engineer who triggered the deploy" },
                          "timestamp": { "type": "string", "description": "ISO timestamp of the deployment" },
                          "status": {
                            "type": "string",
                            "description": "Outcome of this deployment",
                            "enum": ["success", "failed", "rolling_back"]
                          }
                        },
                        "required": ["sha", "author", "timestamp", "status"],
                        "additionalProperties": false
                      }
                    },
                    "active_incidents": {
                      "type": "array",
                      "description": "IDs or summaries of any active incidents",
                      "items": { "type": "string" }
                    }
                  },
                  "required": ["recent_deploys", "active_incidents"],
                  "additionalProperties": false
                },
                "verdict": {
                  "type": "object",
                  "properties": {
                    "ready": { "type": "boolean", "description": "True if the service can proceed to the target version" },
                    "confidence": {
                      "type": "string",
                      "description": "How confident is this verdict?",
                      "enum": ["low", "medium", "high"]
                    },
                    "blockers": {
                      "type": "array",
                      "description": "Reasons the service is NOT ready. Empty if ready=true.",
                      "items": { "type": "string" }
                    },
                    "recommended_next_steps": {
                      "type": "array",
                      "description": "What to do next — regardless of ready/blocked",
                      "items": { "type": "string" }
                    }
                  },
                  "required": ["ready", "confidence", "blockers", "recommended_next_steps"],
                  "additionalProperties": false
                },
                "evidence": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "source": {
                        "type": "string",
                        "description": "Where this evidence came from — RAG retrieval, tool output, or user query",
                        "enum": ["rag", "tool", "user"]
                      },
                      "content": { "type": "string", "description": "The evidence content" },
                      "relevance_score": { "type": ["number", "null"], "description": "0.0–1.0 relevance score from the retriever, if sourced from RAG" }
                    },
                    "required": ["source", "content", "relevance_score"],
                    "additionalProperties": false
                  }
                }
              },
              "required": ["service", "build", "deployment", "verdict", "evidence"],
              "additionalProperties": false
            }""";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private JsonSchemas() {
        // utility class
    }

    /**
     * Build an OpenAI {@code response_format: json_schema} (strict) from a
     * snake_case schema string.
     *
     * @param name       schema name (OpenAI requires a name, max 64 chars)
     * @param schemaJson the JSON schema, as text
     */
    public static ResponseFormat responseFormat(String name, String schemaJson) {
        Map<String, Object> schema;
        try {
            schema = MAPPER.readValue(schemaJson, new TypeReference<>() {
            });
        } catch (Exception e) {
            throw new IllegalArgumentException("Invalid JSON schema for " + name, e);
        }
        ResponseFormat.JsonSchema jsonSchema = ResponseFormat.JsonSchema.builder()
                .name(name)
                .strict(true)
                .schema(schema)
                .build();
        return ResponseFormat.builder()
                .type(ResponseFormat.Type.JSON_SCHEMA)
                .jsonSchema(jsonSchema)
                .build();
    }
}
