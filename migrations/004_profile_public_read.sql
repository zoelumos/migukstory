-- Allow anyone to read public profile display fields (display_name, avatar_url)
-- Still hides: email, provider, metadata, banned_at, is_verified_pro state details
--
-- Without this, the comments component shows "익명" for every author
-- because the profiles join returns null for anon.

-- Column-level grants — anon can only SELECT these 3 columns
grant select (id, display_name, avatar_url) on public.profiles to anon;
grant select (id, display_name, avatar_url) on public.profiles to authenticated;

-- RLS policy — allow SELECT to all roles (grants narrow the column list)
drop policy if exists "public read profile display fields" on public.profiles;
create policy "public read profile display fields" on public.profiles
  for select using (true);

-- Keep the existing "users read own profile" policy too — that one lets
-- authenticated users see ALL their own columns (email, metadata, etc.).
-- Combined: anyone reads (id, display_name, avatar_url); owners read all.
