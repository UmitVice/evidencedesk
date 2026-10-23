---
{
  "tenant": "harbor",
  "source_id": "sandbox-delivery-cap",
  "title": "Sandbox delivery cap",
  "version": 2,
  "status": "active",
  "product": "RelayNest",
  "related": [
    {"source_id": "sandbox-plan-notes", "relation": "conflicts_with"}
  ]
}
---
## Daily cap

Sandbox workspaces accept at most 1000 webhook deliveries per day. Deliveries above the cap are rejected with sandbox_limit_reached until the next UTC day.
