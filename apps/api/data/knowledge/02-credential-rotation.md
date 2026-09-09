---
{
  "tenant": "harbor",
  "source_id": "credential-rotation",
  "title": "Rotate an expired API credential",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Safe rotation

A 401 response with credential_expired means the API credential has reached its expiry date. Create a replacement credential in Settings > API credentials, update the integration secret, and verify a successful request. Revoke the old credential after verification. Never paste credentials into a support ticket.
