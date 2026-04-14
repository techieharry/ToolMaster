---
name: api-integration
description: Build API integrations — REST, WebSocket, webhook handlers. Use when connecting to external services, building scrapers, or wiring up data pipelines.
---

# API Integration

## Process
1. **Read the docs** — find auth method, rate limits, pagination, error codes
2. **Auth first** — get a working authenticated request before anything else
3. **Build incrementally** — one endpoint at a time, verify response shape
4. **Handle failures** — retries with backoff, timeout handling, error parsing
5. **Extract** — parse response into clean data structures

## Patterns

### REST client
- Use requests/httpx (Python) or fetch (JS) — don't build custom HTTP
- Set timeouts on every request (10s default, 30s for large payloads)
- Retry 3x with exponential backoff (1s, 2s, 4s) on 429/500/502/503
- Log request/response on failure, not success

### Rate limiting
- Check response headers: X-RateLimit-Remaining, Retry-After
- Implement token bucket or sliding window
- Never hammer an API — respect limits, your key depends on it

### Error handling
- Parse error response bodies — they usually tell you what's wrong
- Map API errors to your domain errors
- Never swallow errors silently

## Rules
- Never hardcode API keys — use environment variables
- Always set User-Agent header
- Cache responses when the data doesn't change frequently
- Document the API's quirks (undocumented behaviors, known bugs)
