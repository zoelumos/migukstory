#!/usr/bin/env node
/**
 * End-to-end test: simulate a browser anon signup using PUBLISHABLE key.
 * Then verify with PAT (server-side) that the row landed.
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

const url = env.PUBLIC_SUPABASE_URL;
const anonKey = env.PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const pat = env.SUPABASE_ACCESS_TOKEN;
const ref = env.SUPABASE_PROJECT_REF;

const testEmail = `test-${Date.now()}@migukstory.example`;

// 1. Browser-side: POST to PostgREST via publishable key (simulates form submit)
console.log(`📨 Simulating browser signup with email ${testEmail}...`);
const insertRes = await fetch(`${url}/rest/v1/subscribers`, {
	method: 'POST',
	headers: {
		'Content-Type': 'application/json',
		'apikey': anonKey,
		'Authorization': `Bearer ${anonKey}`,
		'Prefer': 'return=representation',
	},
	body: JSON.stringify({
		email: testEmail,
		source: 'test_smoke',
		metadata: { test: true, runner: 'scripts/test_signup_flow.mjs' },
	}),
});
console.log(`  → HTTP ${insertRes.status}`);
console.log(`  → ${(await insertRes.text()).slice(0, 200)}`);

// 2. Server-side verify (via PAT) — anon doesn't have SELECT
console.log(`\n🔍 Verifying via Management API...`);
const checkRes = await fetch(`https://api.supabase.com/v1/projects/${ref}/database/query`, {
	method: 'POST',
	headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${pat}` },
	body: JSON.stringify({ query: `select email, source, created_at, metadata from public.subscribers where email = '${testEmail}';` }),
});
console.log(`  → HTTP ${checkRes.status}`);
console.log(`  → ${await checkRes.text()}`);

// 3. Confirm RLS blocks SELECT from anon
console.log(`\n🔒 Confirming RLS blocks anon SELECT...`);
const denyRes = await fetch(`${url}/rest/v1/subscribers?select=email&limit=1`, {
	headers: { 'apikey': anonKey, 'Authorization': `Bearer ${anonKey}` },
});
console.log(`  → HTTP ${denyRes.status}`);
console.log(`  → ${(await denyRes.text()).slice(0, 200)}`);

// 4. Clean up the test row
console.log(`\n🧹 Cleaning up test row...`);
const cleanRes = await fetch(`https://api.supabase.com/v1/projects/${ref}/database/query`, {
	method: 'POST',
	headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${pat}` },
	body: JSON.stringify({ query: `delete from public.subscribers where email = '${testEmail}' returning email;` }),
});
console.log(`  → ${await cleanRes.text()}`);

// 5. Verify duplicate INSERT returns 23505
console.log(`\n🔁 Testing duplicate-email handling...`);
const e2 = 'duplicate-test@migukstory.example';
await fetch(`${url}/rest/v1/subscribers`, {
	method: 'POST',
	headers: { 'Content-Type': 'application/json', 'apikey': anonKey, 'Authorization': `Bearer ${anonKey}` },
	body: JSON.stringify({ email: e2, source: 'test_dup' }),
});
const dup = await fetch(`${url}/rest/v1/subscribers`, {
	method: 'POST',
	headers: { 'Content-Type': 'application/json', 'apikey': anonKey, 'Authorization': `Bearer ${anonKey}` },
	body: JSON.stringify({ email: e2, source: 'test_dup_2' }),
});
console.log(`  → 2nd insert HTTP ${dup.status} (expecting 409 or 23505 error)`);
console.log(`  → ${(await dup.text()).slice(0, 200)}`);

// Clean up the dup test
await fetch(`https://api.supabase.com/v1/projects/${ref}/database/query`, {
	method: 'POST',
	headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${pat}` },
	body: JSON.stringify({ query: `delete from public.subscribers where email = '${e2}';` }),
});

console.log(`\n✅ All checks complete.`);
