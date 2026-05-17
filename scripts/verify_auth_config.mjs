#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const env = Object.fromEntries(
	readFileSync(join(resolve(__dirname, '..'), '.env'), 'utf8')
		.split('\n').filter((l) => l && !l.startsWith('#') && l.includes('='))
		.map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
);

const res = await fetch(`https://api.supabase.com/v1/projects/${env.SUPABASE_PROJECT_REF}/config/auth`, {
	headers: { 'Authorization': `Bearer ${env.SUPABASE_ACCESS_TOKEN}` },
});
const cfg = await res.json();

console.log('Auth config summary:');
console.log('  site_url            :', cfg.site_url);
console.log('  external_google_*   :', cfg.external_google_enabled ? '✅ ENABLED' : '❌ disabled');
console.log('  external_email_*    :', cfg.external_email_enabled !== false ? '✅ (email/magic-link enabled)' : 'disabled');
console.log('  disable_signup      :', cfg.disable_signup ? '❌ signups blocked' : '✅ open');
console.log('  uri_allow_list      :', (cfg.uri_allow_list || '').split(',').slice(0, 4).join(' / ') + ' …');
console.log('  jwt_exp             :', cfg.jwt_exp, 'sec');
console.log('  mfa_max_factors     :', cfg.mfa_max_enrolled_factors);
