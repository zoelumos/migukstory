#!/usr/bin/env node
/**
 * Tighten Supabase auth config:
 *  - Remove localhost from production uri_allow_list (phishing prevention)
 *  - Enable Postgres audit logging
 *  - Confirm refresh_token_rotation + jwt_exp sensible defaults
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

const body = {
	site_url: 'https://migukstory.com',
	uri_allow_list: [
		'https://migukstory.com',
		'https://migukstory.com/**',
		'https://www.migukstory.com',
		'https://www.migukstory.com/**',
	].join(','),  // ← localhost removed for production
	jwt_exp: 3600,
	refresh_token_rotation_enabled: true,
	security_refresh_token_reuse_interval: 10,
	audit_log_disable_postgres: false,           // ← enable audit log to Postgres
};

const res = await fetch(`https://api.supabase.com/v1/projects/${env.SUPABASE_PROJECT_REF}/config/auth`, {
	method: 'PATCH',
	headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${env.SUPABASE_ACCESS_TOKEN}` },
	body: JSON.stringify(body),
});

console.log(`HTTP ${res.status}`);
const text = await res.text();
console.log(text.slice(0, 500));
if (!res.ok) process.exit(1);
console.log('\n✅ Auth hardening applied.');
