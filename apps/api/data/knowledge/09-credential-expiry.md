---
{
  "tenant": "harbor",
  "source_id": "credential-expiry",
  "title": "Credential lifetime",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Expiry policy

New RelayNest API credentials expire after 90 days. The owner can select an earlier expiry during creation. Existing credentials cannot have their expiry extended. A replacement is required. Expiry is evaluated in UTC.
