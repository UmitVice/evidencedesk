---
{
  "tenant": "harbor",
  "source_id": "api-rate-limits",
  "title": "API rate limits",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Retry guidance

The standard API permits 60 requests per minute per workspace. A 429 response includes Retry-After in seconds. Stop sending requests until that period ends. Rapid retries consume the same workspace limit.
