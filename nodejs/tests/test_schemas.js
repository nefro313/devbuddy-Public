/**
 * Tests for src/schemas.js — Week 2 (Node.js)
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

import {
  BuildCheckSchema,
  ServiceReadinessReportSchema,
  DeployRecordSchema,
  analyzePr,
} from "../src/schemas.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const dataDir = resolve(__dirname, "..", "..", "shared", "data");

// ═══════════════════════════════════════════════════════════════
// BuildCheck — in-session schema (requires OpenRouter)
// ═══════════════════════════════════════════════════════════════

describe("BuildCheck", () => {
  it("validates a valid BuildCheck object", () => {
    const bc = BuildCheckSchema.parse({
      project: "auth-service",
      severity: "high",
      summary: "Fixed login redirect loop",
      affected_files: ["src/auth.py", "tests/test_auth.py"],
    });
    expect(bc.project).toBe("auth-service");
    expect(bc.severity).toBe("high");
  });

  it("rejects invalid severity", () => {
    expect(() =>
      BuildCheckSchema.parse({
        project: "auth-service",
        severity: "INVALID",
        summary: "test",
        affected_files: ["app.js"],
      })
    ).toThrow();
  });

  it("rejects missing fields", () => {
    expect(() =>
      BuildCheckSchema.parse({
        project: "auth-service",
        // severity missing
        summary: "test",
        affected_files: ["app.js"],
      })
    ).toThrow();
  });
});

// ═══════════════════════════════════════════════════════════════
// analyzePr — requires OpenRouter
// ═══════════════════════════════════════════════════════════════

describe("analyzePr", () => {
  it("returns a typed object, not prose", async () => {
    const diff = "Fix login bug\n\nChanged auth.py line 42";
    const result = await analyzePr({
      title: "Fix login bug",
      diff,
      temperature: 0.0,
    });

    expect(result).toBeTruthy();
    expect(result.project).toBeTruthy();
    expect(["low", "medium", "high", "critical"]).toContain(result.severity);
    expect(result.summary).toBeTruthy();
    expect(result.affected_files.length).toBeGreaterThan(0);
  });

  it("is deterministic at temperature=0", async () => {
    const diff = "Fix login bug\n\nChanged auth.py line 42";
    const r1 = await analyzePr({ title: "Fix login bug", diff, temperature: 0.0 });
    const r2 = await analyzePr({ title: "Fix login bug", diff, temperature: 0.0 });
    expect(r1.severity).toBe(r2.severity);
  });

  it("works with sample diff from shared/data", async () => {
    const diff = readFileSync(
      resolve(dataDir, "sample-diff.txt"),
      "utf-8"
    );
    const result = await analyzePr({
      title: "Fix login redirect loop in auth-service",
      diff,
      temperature: 0.0,
      maxTokens: 200,
    });
    expect(result.project).toBeTruthy();
    expect(result.severity).toBeTruthy();
  }, 60_000);
});

// ═══════════════════════════════════════════════════════════════
// ServiceReadinessReport — pure Zod schema tests (no API calls)
// ═══════════════════════════════════════════════════════════════

describe("ServiceReadinessReport", () => {
  it("validates the healthy reference scenario", () => {
    const data = JSON.parse(
      readFileSync(
        resolve(dataDir, "service-readiness-healthy.json"),
        "utf-8"
      )
    );
    const report = ServiceReadinessReportSchema.parse(data);
    expect(report.service.name).toBe("auth-service");
    expect(report.build.status).toBe("healthy");
    expect(report.verdict.ready).toBe(true);
    expect(report.verdict.confidence).toBe("high");
    expect(report.verdict.blockers).toEqual([]);
    expect(report.evidence.length).toBe(2);
  });

  it("validates the degraded scenario", () => {
    const data = JSON.parse(
      readFileSync(
        resolve(dataDir, "service-readiness-degraded.json"),
        "utf-8"
      )
    );
    const report = ServiceReadinessReportSchema.parse(data);
    expect(report.build.status).toBe("degraded");
    expect(report.build.failing_since).toBeTruthy();
    expect(report.verdict.ready).toBe(false);
    expect(report.verdict.blockers.length).toBeGreaterThan(0);
  });

  it("validates the unknown scenario", () => {
    const data = JSON.parse(
      readFileSync(
        resolve(dataDir, "service-readiness-unknown.json"),
        "utf-8"
      )
    );
    const report = ServiceReadinessReportSchema.parse(data);
    expect(report.build.status).toBe("unknown");
    expect(report.verdict.confidence).toBe("low");
  });

  // ── Cross-field invariants ──────────────────────────────────

  it("rejects ready=true with blockers", () => {
    const data = {
      service: { name: "test-svc", version: "1.0.0", owner_team: "qa" },
      build: {
        status: "healthy",
        last_deploy: "2026-06-28T00:00:00Z",
        failing_since: null,
      },
      deployment: { recent_deploys: [], active_incidents: [] },
      verdict: {
        ready: true,
        confidence: "high",
        blockers: ["build is red"],
        recommended_next_steps: [],
      },
      evidence: [
        {
          source: "tool",
          content: "build=green",
          relevance_score: null,
        },
      ],
    };
    expect(() => ServiceReadinessReportSchema.parse(data)).toThrow(
      /Contradiction|ready/
    );
  });

  it("rejects not-ready with high confidence and no blockers", () => {
    const data = {
      service: { name: "test-svc", version: "1.0.0", owner_team: "qa" },
      build: {
        status: "healthy",
        last_deploy: "2026-06-28T00:00:00Z",
        failing_since: null,
      },
      deployment: { recent_deploys: [], active_incidents: [] },
      verdict: {
        ready: false,
        confidence: "high",
        blockers: [],
        recommended_next_steps: [],
      },
      evidence: [],
    };
    expect(() => ServiceReadinessReportSchema.parse(data)).toThrow();
  });

  it("rejects degraded status with no failing_since", () => {
    const data = {
      service: { name: "test-svc", version: "1.0.0", owner_team: "qa" },
      build: {
        status: "degraded",
        last_deploy: "2026-06-28T00:00:00Z",
        failing_since: null,
      },
      deployment: { recent_deploys: [], active_incidents: [] },
      verdict: {
        ready: false,
        confidence: "low",
        blockers: ["build degraded"],
        recommended_next_steps: [],
      },
      evidence: [],
    };
    expect(() => ServiceReadinessReportSchema.parse(data)).toThrow(
      /failing_since/
    );
  });

  it("rejects invalid DeployRecord status", () => {
    expect(() =>
      DeployRecordSchema.parse({
        sha: "abc123",
        author: "test",
        timestamp: "2026-06-28T00:00:00Z",
        status: "in_progress", // not in enum
      })
    ).toThrow();
  });

  it("round-trips through JSON", () => {
    const data = JSON.parse(
      readFileSync(
        resolve(dataDir, "service-readiness-healthy.json"),
        "utf-8"
      )
    );
    const report = ServiceReadinessReportSchema.parse(data);
    const dumped = JSON.parse(JSON.stringify(report));
    const reloaded = ServiceReadinessReportSchema.parse(dumped);
    expect(reloaded.service.name).toBe(report.service.name);
    expect(reloaded.verdict.ready).toBe(report.verdict.ready);
  });
});
