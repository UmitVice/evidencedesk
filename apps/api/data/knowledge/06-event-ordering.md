---
{
  "tenant": "harbor",
  "source_id": "event-ordering",
  "title": "Event ordering and duplicates",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Delivery semantics

RelayNest does not guarantee webhook event order. Every event includes an event ID and an occurred_at timestamp. Store processed event IDs and make duplicate event handling idempotent. Do not infer state solely from delivery arrival order.
