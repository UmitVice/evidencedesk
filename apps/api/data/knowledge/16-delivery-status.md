---
{
  "tenant": "harbor",
  "source_id": "delivery-status",
  "title": "Delivery log statuses",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Status definitions

Pending means no attempt has completed. Delivered means the receiver returned 2xx in time. Retrying means another automatic attempt is scheduled. Exhausted means automatic attempts ended. A manual replay is recorded separately and does not erase earlier failures.
