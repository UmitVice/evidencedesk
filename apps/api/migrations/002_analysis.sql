CREATE TABLE evidence.runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), session_id uuid NOT NULL, tenant text NOT NULL,
 ticket_id uuid NOT NULL, ticket_version integer NOT NULL,
 mode text NOT NULL CHECK(mode IN ('simulated','live')),
 status text NOT NULL CHECK(status IN ('running','complete','failed')),
 question text NOT NULL, evidence jsonb NOT NULL DEFAULT '[]', result jsonb,
 trace jsonb NOT NULL DEFAULT '{}', error_code text,
 created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 FOREIGN KEY(ticket_id,session_id,tenant) REFERENCES evidence.tickets(id,session_id,tenant)
 ON DELETE CASCADE, UNIQUE(id,session_id,tenant)
);
CREATE INDEX runs_owner ON evidence.runs(session_id,tenant,ticket_id,created_at DESC);
GRANT SELECT,INSERT,UPDATE ON evidence.runs TO evidencedesk_runtime;
REVOKE ALL ON evidence.runs FROM PUBLIC;
