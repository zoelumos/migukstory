-- Fix: grant anon role INSERT permission on subscribers
-- The "Automatically expose new tables" setting was disabled (correct for security),
-- so we must explicitly grant the privileges that RLS then narrows.

-- Schema-level usage (anon needs to "see" public schema exists)
grant usage on schema public to anon;
grant usage on schema public to authenticated;

-- Subscribers: anon needs INSERT (RLS policy narrows what they can insert)
grant insert on public.subscribers to anon;

-- Profiles: authenticated needs SELECT + UPDATE on own row (RLS narrows)
grant select, update on public.profiles to authenticated;

-- Comments: everyone can SELECT non-hidden, authenticated can CRUD own
grant select on public.comments to anon;                  -- public readable
grant select, insert, update, delete on public.comments to authenticated;
