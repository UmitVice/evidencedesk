CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS evidence;
REVOKE ALL ON SCHEMA evidence FROM PUBLIC;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evidencedesk_runtime') THEN
    CREATE ROLE evidencedesk_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END $$;
CREATE TABLE evidence.sessions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant text NOT NULL CHECK (tenant IN ('harbor','summit')),
 token_hash text NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 UNIQUE(id, tenant)
);
CREATE TABLE evidence.documents (
 id uuid PRIMARY KEY, tenant text NOT NULL CHECK (tenant IN ('harbor','summit')),
 source_id text NOT NULL, title text NOT NULL, version integer NOT NULL CHECK(version > 0),
 status text NOT NULL CHECK(status IN ('active','obsolete')), content_hash text NOT NULL,
 UNIQUE(tenant, source_id, version), UNIQUE(id,tenant)
);
CREATE UNIQUE INDEX one_active_document ON evidence.documents(tenant,source_id) WHERE status='active';
CREATE TABLE evidence.chunks (
 id uuid PRIMARY KEY, document_id uuid NOT NULL, tenant text NOT NULL,
 heading text NOT NULL, body text NOT NULL CHECK(length(body) <= 8000), content_hash text NOT NULL,
 embedding vector(384), embedding_manifest jsonb NOT NULL,
 search tsvector GENERATED ALWAYS AS (to_tsvector('english', heading || ' ' || body)) STORED,
 FOREIGN KEY(document_id,tenant) REFERENCES evidence.documents(id,tenant) ON DELETE CASCADE
);
CREATE INDEX chunks_owner ON evidence.chunks(tenant,document_id);
CREATE INDEX chunks_search ON evidence.chunks USING gin(search);
CREATE TABLE evidence.tickets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), session_id uuid NOT NULL, tenant text NOT NULL,
 sample text NOT NULL, title text NOT NULL, body text NOT NULL, version integer NOT NULL DEFAULT 1,
 FOREIGN KEY(session_id,tenant) REFERENCES evidence.sessions(id,tenant) ON DELETE CASCADE,
 UNIQUE(id,session_id,tenant)
);
CREATE INDEX tickets_owner ON evidence.tickets(session_id,tenant);
CREATE TABLE evidence.usage_counters (
 key text PRIMARY KEY, count integer NOT NULL CHECK(count >= 0), expires_at timestamptz NOT NULL
);
GRANT USAGE ON SCHEMA evidence TO evidencedesk_runtime;
GRANT SELECT ON evidence.documents,evidence.chunks TO evidencedesk_runtime;
GRANT SELECT,INSERT,UPDATE,DELETE ON evidence.sessions,evidence.tickets,evidence.usage_counters TO evidencedesk_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA evidence FROM PUBLIC;
