# Payment API — Internal Specification

> Last updated: 2026-06-15
> Owner: payments team

## Endpoints

### POST /v1/payments
Create a new payment. Requires `amount`, `currency`, `source_id`.

**Rate limit:** 100 req/s per tenant.
**Timeout:** 30 seconds (configurable via `PAYMENT_TIMEOUT_MS` env var).
**Idempotency:** Pass `Idempotency-Key` header to safely retry.

### GET /v1/payments/{id}
Retrieve a payment by ID. Returns status: `pending`, `completed`, `failed`, `refunded`.

### POST /v1/payments/{id}/refund
Refund a completed payment. Partial refunds supported via `amount` field.

### GET /v1/payments/health
Health check. Returns `{"status": "ok", "db": "connected"}`.

## Authentication
All endpoints require `Authorization: Bearer <api-key>`. API keys are provisioned per tenant via the payments-admin dashboard.

## Error Codes
| Code | Meaning |
|------|---------|
| 402  | Insufficient funds |
| 408  | Payment processing timeout |
| 429  | Rate limit exceeded |
| 503  | Downstream processor unavailable |

## SLA
Payment API SLA: 99.95% uptime. P99 latency < 500ms. Incident response: 15 minutes for Sev1, 1 hour for Sev2.
