CREATE TABLE evidence.proposals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL UNIQUE,
 session_id uuid NOT NULL, tenant text NOT NULL, ticket_id uuid NOT NULL,
 expected_version integer NOT NULL, content text NOT NULL CHECK(length(content) BETWEEN 1 AND 1200),
 content_hash text NOT NULL CHECK(content_hash=encode(sha256(convert_to(content,'UTF8')),'hex')),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','applied','rejected')),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 decided_at timestamptz,
 FOREIGN KEY(run_id,session_id,tenant) REFERENCES evidence.runs(id,session_id,tenant) ON DELETE CASCADE,
 FOREIGN KEY(ticket_id,session_id,tenant) REFERENCES evidence.tickets(id,session_id,tenant) ON DELETE CASCADE,
 UNIQUE(id,session_id,tenant,ticket_id)
);
CREATE INDEX proposals_owner ON evidence.proposals(session_id,tenant,ticket_id);
CREATE TABLE evidence.notes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), proposal_id uuid NOT NULL UNIQUE,
 session_id uuid NOT NULL, tenant text NOT NULL, ticket_id uuid NOT NULL, content text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(proposal_id,session_id,tenant,ticket_id)
 REFERENCES evidence.proposals(id,session_id,tenant,ticket_id) ON DELETE CASCADE
);
CREATE INDEX notes_owner ON evidence.notes(session_id,tenant,ticket_id);
CREATE TABLE evidence.audit_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), session_id uuid NOT NULL, tenant text NOT NULL,
 ticket_id uuid NOT NULL, proposal_id uuid NOT NULL,
 event text NOT NULL CHECK(event IN ('proposed','applied','rejected')),
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(proposal_id,session_id,tenant,ticket_id)
 REFERENCES evidence.proposals(id,session_id,tenant,ticket_id) ON DELETE CASCADE,
 UNIQUE(proposal_id,event)
);
CREATE INDEX audit_owner ON evidence.audit_events(session_id,tenant,ticket_id);
CREATE FUNCTION evidence.guard_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.id,NEW.run_id,NEW.session_id,NEW.tenant,NEW.ticket_id,NEW.expected_version,
     NEW.content,NEW.content_hash,NEW.created_at,NEW.expires_at)
 IS DISTINCT FROM
    (OLD.id,OLD.run_id,OLD.session_id,OLD.tenant,OLD.ticket_id,OLD.expected_version,
     OLD.content,OLD.content_hash,OLD.created_at,OLD.expires_at) THEN
   RAISE EXCEPTION 'Proposal content and ownership are immutable';
 END IF;
 IF OLD.status <> 'pending' OR NEW.status NOT IN ('applied','rejected') OR NEW.decided_at IS NULL THEN
   RAISE EXCEPTION 'Invalid proposal transition';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER proposal_immutable BEFORE UPDATE ON evidence.proposals
FOR EACH ROW EXECUTE FUNCTION evidence.guard_proposal();
GRANT SELECT,INSERT ON evidence.proposals,evidence.notes,evidence.audit_events TO evidencedesk_runtime;
GRANT UPDATE(status,decided_at) ON evidence.proposals TO evidencedesk_runtime;
REVOKE ALL ON evidence.proposals,evidence.notes,evidence.audit_events FROM PUBLIC;
