#!/usr/bin/env node
/**
 * Enable Google OAuth provider in Supabase via Management API.
 * Reads credentials from .env (never logs them).
 *
 * Endpoint: PATCH /v1/projects/{ref}/config/auth
 * Docs: https://supabase.com/docs/reference/api/v1-update-a-projects-auth-config
 */
import { readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const env = Object.fromEntries(
	readFileSync(join(resolve(__dirname, '..'), '.env'), 'utf8')
		.split('\n').filter((l) => l && !l.startsWith('#') && l.includes('='))
		.map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
);

const ref = env.SUPABASE_PROJECT_REF;
const tok = env.SUPABASE_ACCESS_TOKEN;
const gid = env.GOOGLE_OAUTH_CLIENT_ID;
const gsc = env.GOOGLE_OAUTH_CLIENT_SECRET;
const siteUrl = 'https://migukstory.com';

if (!ref || !tok || !gid || !gsc) {
	console.error('Missing env vars'); process.exit(1);
}

const body = {
	external_google_enabled: true,
	external_google_client_id: gid,
	external_google_secret: gsc,
	external_google_skip_nonce_check: false,
	site_url: siteUrl,
	// Production allowlist only (localhost removed — minor phishing prevention)
	uri_allow_list: [
		'https://migukstory.com',
		'https://migukstory.com/**',
		'https://www.migukstory.com',
		'https://www.migukstory.com/**',
	].join(','),
	// Security hardening
	jwt_exp: 3600,
	refresh_token_rotation_enabled: true,
	security_refresh_token_reuse_interval: 10,
	audit_log_disable_postgres: false,
};

console.log(`⚙️  Configuring Google OAuth on project ${ref}...`);
console.log(`   site_url: ${siteUrl}`);
console.log(`   client_id: ${gid.slice(0, 12)}…${gid.slice(-30)}`);

const res = await fetch(`https://api.supabase.com/v1/projects/${ref}/config/auth`, {
	method: 'PATCH',
	headers: {
		'Content-Type': 'application/json',
		'Authorization': `Bearer ${tok}`,
	},
	body: JSON.stringify(body),
});

const text = await res.text();
console.log(`HTTP ${res.status}`);
console.log(text.slice(0, 800));

if (!res.ok) process.exit(1);
console.log('\n✅ Google OAuth provider enabled on Supabase.');
console.log('   Callback URL: https://hoemvraesebfvtkkjbdx.supabase.co/auth/v1/callback');
console.log('   (already configured on the Google OAuth Client)');
