---
{
  "tenant": "harbor",
  "source_id": "webhook-signatures",
  "title": "Verify webhook signatures",
  "version": 2,
  "status": "active",
  "product": "RelayNest"
}
---
## Verification rules

RelayNest signs the raw request body using HMAC-SHA256. Compare the signature using a constant-time function. Reject timestamps older than five minutes. Signature verification uses the webhook signing secret, not an API credential.
