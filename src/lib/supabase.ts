import { createClient } from '@supabase/supabase-js';

/**
 * Supabase client for migukstory.com — browser-safe (publishable key).
 *
 * Project: hoemvraesebfvtkkjbdx (US East)
 * Tables:
 *   - subscribers      (newsletter signups, INSERT-only RLS for anon)
 *   - profiles         (future — Google OAuth user metadata, RLS user_id = auth.uid())
 *   - comments         (future — per-article threads, INSERT for auth.uid(), SELECT all)
 *
 * Server-side admin operations (banning users, password resets, querying
 * as service role) belong in scripts/ or Cloudflare Workers, NOT here.
 */

const SUPABASE_URL = import.meta.env.PUBLIC_SUPABASE_URL;
const SUPABASE_KEY = import.meta.env.PUBLIC_SUPABASE_PUBLISHABLE_KEY;

if (!SUPABASE_URL || !SUPABASE_KEY) {
	throw new Error(
		'Missing PUBLIC_SUPABASE_URL or PUBLIC_SUPABASE_PUBLISHABLE_KEY in env. ' +
		'See .env.example.'
	);
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, {
	auth: {
		persistSession: true,            // keep session across page loads / nav
		autoRefreshToken: true,          // refresh JWT before it expires (1h default)
		detectSessionInUrl: true,        // pick up OAuth #access_token=... fragment on /auth/callback
		flowType: 'pkce',                // recommended OAuth flow for SPAs/static sites
	},
});

// Type for the subscribers table (matches migrations/001_subscribers.sql schema)
export interface Subscriber {
	id: string;          // uuid
	email: string;
	source: string;      // 'newsletter_form' | 'first-30-days-magnet' | 'manual' | ...
	created_at: string;  // ISO timestamp
	confirmed_at: string | null;
	unsubscribed_at: string | null;
	metadata: Record<string, unknown> | null;
}
