REVOKE ALL ON public.evidencedesk_migrations FROM PUBLIC;
DO $$
DECLARE api_role text;
BEGIN
  FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
      EXECUTE format('REVOKE ALL ON public.evidencedesk_migrations FROM %I', api_role);
      EXECUTE format('REVOKE ALL ON SCHEMA evidence FROM %I', api_role);
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA evidence FROM %I', api_role);
    END IF;
  END LOOP;
END $$;
