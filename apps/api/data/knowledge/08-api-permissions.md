---
{
  "tenant": "harbor",
  "source_id": "api-permissions",
  "title": "API credential permissions",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Least privilege

Credentials can have read-events, write-events, or export permissions. A 403 response means the credential lacks the required permission. Workspace owners may create a replacement with the needed scope. An expired credential instead produces 401.
