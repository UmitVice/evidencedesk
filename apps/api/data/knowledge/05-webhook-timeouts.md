---
{
  "tenant": "harbor",
  "source_id": "webhook-timeouts",
  "title": "Webhook timeout handling",
  "version": 2,
  "status": "active",
  "product": "RelayNest",
  "related": [
    {"source_id": "webhook-retries", "relation": "depends_on"}
  ]
}
---
## Response deadline

The receiving endpoint must acknowledge a delivery with a 2xx response within ten seconds. Process long-running work after acknowledgment. A timeout is recorded as a failed delivery and follows the standard webhook retry schedule.
