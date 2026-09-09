---
{
  "tenant": "harbor",
  "source_id": "export-format",
  "title": "CSV export format",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Encoding and timestamps

RelayNest exports UTF-8 CSV with a header row. Event times use ISO 8601 in UTC. Spreadsheet applications may display timestamps in a local time zone. The event_id column is stable across repeat exports.
