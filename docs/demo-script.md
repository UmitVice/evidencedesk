# Five-minute demo

1. Open the home page and select a sample ticket; **Webhook retry failure** is marked **Try this first**. Its ticket opens directly; no model runs yet.
2. Select **Analyze ticket**. Read the result's actual mode and each claim. Open **View source** to compare the claim, exact quote, full source passage, version, and status. Escape returns focus to the source button.
3. Review the exact draft under **Review the internal note**. Refresh while pending to demonstrate persistence. The answer is not a saved note.
4. Choose **Reject draft**. The ticket version and saved-note list remain unchanged; the audit records rejection.
5. Analyze again within the quota, then **Approve & save note**. Refresh to show the exact persisted note and audit event. The BFF/integration checks separately verify repeated approval creates no duplicate.
6. Expand **Ask a different question (optional)**. In simulated mode choose the supplied SSO question. In live mode ask a question outside RelayNest documentation; missing evidence should abstain without a proposal, and invalid model output must fail safely. Never promise perfect abstention.
7. Open Evaluations. Distinguish the full support-v3 live run, preserved historical/smoke records, deterministic fixture retrieval, separate database safety tests, and pending human quality review.

Screenshots are from the running local fixture application, labeled as such. They are not fabricated live results or a video recording. Hosted dev and production use separate verified Ohio databases.
