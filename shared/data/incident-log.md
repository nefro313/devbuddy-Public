# Production Incidents — June 2026

## INC-842 — payment-api latency spike
**Date:** 2026-06-28
**Severity:** Sev1
**Status:** Resolved
**Error code:** 408 (timeout)
**Root cause:** Database connection pool exhausted under peak load. Increased pool size from 20 to 50.
**Affected:** 15% of requests for 45 minutes.

## INC-799 — auth-service token validation failure
**Date:** 2026-06-25
**Severity:** Sev2
**Status:** Resolved
**Error code:** 401
**Root cause:** Expired token cache not invalidated after deployment. Cache TTL reduced from 1h to 15m.
**Affected:** 3% of login attempts for 2 hours.

## INC-901 — inventory-service data inconsistency
**Date:** 2026-06-22
**Severity:** Sev3
**Status:** Investigating
**Error code:** 500
**Tracking:** PROJ-891, PROJ-892
**Notes:** Inventory counts diverging between primary and replica. No customer impact yet. Engineering: catalog team investigating replication lag.
