---
{
  "tenant": "harbor",
  "source_id": "webhook-retries",
  "title": "Webhook retry schedule",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Delivery recovery

RelayNest retries failed webhooks after 1 minute, 5 minutes, 30 minutes, and 2 hours. A delivery that still fails is marked exhausted. Fix the receiving endpoint, then choose Replay delivery in the delivery log. Replay creates a new delivery attempt with the original event ID. Receivers must deduplicate by event ID.
