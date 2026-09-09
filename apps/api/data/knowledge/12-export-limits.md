---
{
  "tenant": "harbor",
  "source_id": "export-limits",
  "title": "Export size limits",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Splitting exports

An export contains at most 100000 events. If the job reports result_too_large, split the requested time interval into smaller ranges. Completed exports remain available for seven days. The interface reports job status separately from download-link status.
