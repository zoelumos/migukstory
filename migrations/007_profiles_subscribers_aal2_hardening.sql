-- migukstory.com — Phase 1b auth/admin hardening
--
-- 1. Remove unauthenticated exposure of profiles.is_admin by replacing the anon
--    column-level SELECT grant with only public-safe display columns.
-- 2. Require AAL2 (verified MFA) for admin profile writes, mirroring the
--    comments admin write/delete guard added in migration 006.
-- 3. Allow authenticated admins to read subscribers through RLS-backed server
--    Pages Functions, so the browser never needs a service-role key.
--
-- Run via: node scripts/run_migration.mjs migrations/007_profiles_subscribers_aal2_hardening.sql

-- Re-scope anon profile reads: no is_admin, email, provider, or metadata.
revoke select on public.profiles from anon;
grant select (id, display_name, avatar_url, created_at) on public.profiles to anon;

-- Admin profile writes require AAL2. Restrictive policies AND with permissive
-- profile update policies, so non-admin own-profile updates remain governed by
-- the existing policy while admin writes need MFA.
drop policy if exists "restrict_admin_profile_writes_to_aal2" on public.profiles;
create policy "restrict_admin_profile_writes_to_aal2"
  on public.profiles
  as restrictive
  for update
  to authenticated
  using (
    public.current_user_role() != 'admin'
    or public.current_user_aal() = 'aal2'
  )
  with check (
    public.current_user_role() != 'admin'
    or public.current_user_aal() = 'aal2'
  );

-- Admin dashboard can read newsletter signups without exposing subscribers to anon.
drop policy if exists "admins read subscribers" on public.subscribers;
create policy "admins read subscribers"
  on public.subscribers
  for select
  to authenticated
  using (public.current_user_role() = 'admin');
