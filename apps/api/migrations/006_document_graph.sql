-- Document-level relations used as a retrieval signal. Both endpoints carry the edge tenant in
-- their foreign keys, so an edge can never connect documents from different tenants.
CREATE TABLE evidence.document_edges (
 tenant text NOT NULL CHECK (tenant IN ('harbor','summit')),
 from_document uuid NOT NULL, to_document uuid NOT NULL,
 relation text NOT NULL CHECK (relation IN ('supersedes','conflicts_with','depends_on','see_also')),
 origin text NOT NULL CHECK (origin IN ('version','front_matter')),
 PRIMARY KEY (tenant, from_document, to_document, relation),
 CHECK (from_document <> to_document),
 FOREIGN KEY (from_document, tenant) REFERENCES evidence.documents(id, tenant) ON DELETE CASCADE,
 FOREIGN KEY (to_document, tenant) REFERENCES evidence.documents(id, tenant) ON DELETE CASCADE
);
CREATE INDEX document_edges_to ON evidence.document_edges(tenant, to_document);
GRANT SELECT ON evidence.document_edges TO evidencedesk_runtime;
REVOKE ALL ON evidence.document_edges FROM PUBLIC;
DO $$
DECLARE api_role text;
BEGIN
  FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
      EXECUTE format('REVOKE ALL ON evidence.document_edges FROM %I', api_role);
    END IF;
  END LOOP;
END $$;
