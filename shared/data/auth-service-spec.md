# Auth Service — API Specification

> Last updated: 2026-06-25
> Owner: platform-identity

## Endpoints

### POST /v1/auth/login
Authenticate a user. Returns JWT token with 1h expiry.

### POST /v1/auth/refresh
Refresh an expired token. Requires valid refresh token.

### GET /v1/auth/validate
Validate a token. Returns `{"valid": true}` or `{"valid": false}`.

## Error Codes
| Code | Meaning |
|------|---------|
| 401  | Invalid or expired token |
| 403  | Insufficient permissions |
| 429  | Rate limit exceeded (100 req/min per user) |

## SLA
Auth service SLA: 99.99% uptime. P99 latency < 100ms.
Incident response: 5 minutes for Sev1.
