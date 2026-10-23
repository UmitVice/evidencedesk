---
{
  "tenant": "harbor",
  "source_id": "delivery-replay",
  "title": "Manual delivery replay conditions",
  "version": 2,
  "status": "active",
  "product": "RelayNest",
  "related": [
    {"source_id": "event-retention", "relation": "depends_on"},
    {"source_id": "api-permissions", "relation": "depends_on"}
  ]
}
---
## Replay conditions

A manual replay sends the stored payload of the original event again. Replay is only possible while the original event is still inside the workspace event retention window. Starting a replay requires the write-events permission. A replay of an event that has aged out fails with event_expired.
