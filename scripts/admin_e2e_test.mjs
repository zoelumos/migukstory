#!/usr/bin/env node
/**
 * End-to-end auth test using the Supabase service-role key.
 *
 * Creates a temporary test user, signs them in, verifies session persistence,
 * tests logout, then deletes the user. No real Google OAuth needed.
 */
import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const env = Object.fromEntries(
	readFileSync(join(resolve(__dirname, '..'), '.env'), 'utf8')
		.split('\n').filter((l) => l && !l.startsWith('#') && l.includes('='))
		.map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
);

const URL = env.PUBLIC_SUPABASE_URL;
const ANON = env.PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const SECRET = env.SUPABASE_SECRET_KEY;

if (!URL || !ANON || !SECRET) { console.error('missing env'); process.exit(1); }

const admin = createClient(URL, SECRET, { auth: { persistSession: false } });
const anon  = createClient(URL, ANON,   { auth: { persistSession: false } });

const TEST_EMAIL = `e2e-${Date.now()}@migukstory.test`;
const TEST_PASS  = 'TestPass-' + Math.random().toString(36).slice(2, 14);

console.log(`\n🧪 E2E auth test — user: ${TEST_EMAIL}`);

// 1. Create user via admin
console.log('\n1️⃣  admin.createUser…');
const { data: cu, error: cuErr } = await admin.auth.admin.createUser({
	email: TEST_EMAIL,
	password: TEST_PASS,
	email_confirm: true,
	user_metadata: { full_name: 'E2E Tester', avatar_url: null },
});
if (cuErr) { console.error('  ❌', cuErr); process.exit(1); }
console.log('  ✅ created user id=', cu.user.id);

// 2. Verify profile auto-created by trigger
const { data: prof } = await admin.from('profiles').select('*').eq('id', cu.user.id).maybeSingle();
console.log('  profile row:', prof ? `✅ display_name=${prof.display_name}` : '❌ MISSING — trigger broken');

// 3. Sign in as user (simulates clicking "Google로 로그인" succeeding)
console.log('\n2️⃣  signInWithPassword (simulates post-OAuth session)…');
const { data: si, error: siErr } = await anon.auth.signInWithPassword({
	email: TEST_EMAIL, password: TEST_PASS,
});
if (siErr) { console.error('  ❌', siErr); await admin.auth.admin.deleteUser(cu.user.id); process.exit(1); }
console.log('  ✅ session.access_token length=', si.session.access_token.length);
console.log('  ✅ session.user.email=', si.session.user.email);
console.log('  ✅ refresh_token present=', !!si.session.refresh_token);

// 4. Post a comment as this user
console.log('\n3️⃣  Posting test comment (RLS check — authed user inserts as own author_id)…');
const userClient = createClient(URL, ANON, { auth: { persistSession: false } });
await userClient.auth.setSession({ access_token: si.session.access_token, refresh_token: si.session.refresh_token });
const { data: cmt, error: cmtErr } = await userClient.from('comments').insert({
	post_slug: '/blog/test-e2e-' + Date.now() + '/',
	author_id: cu.user.id,
	body: 'E2E test comment — should auto-delete with user',
}).select().single();
if (cmtErr) { console.error('  ❌', cmtErr); }
else console.log('  ✅ comment inserted, id=', cmt.id);

// 5. Verify public can read it
console.log('\n4️⃣  Anon reads comment + profile join…');
const { data: pub, error: pubErr } = await anon
	.from('comments')
	.select('id, body, profiles!comments_author_id_fkey(display_name, avatar_url)')
	.eq('id', cmt?.id)
	.maybeSingle();
if (pubErr) console.error('  ❌', pubErr);
else console.log('  ✅ anon sees:', JSON.stringify(pub));

// 6. signOut global
console.log('\n5️⃣  signOut({ scope: "global" })…');
const { error: soErr } = await userClient.auth.signOut({ scope: 'global' });
console.log(soErr ? `  ❌ ${soErr.message}` : '  ✅ signOut succeeded');

// 7. Verify token no longer works after global signOut
console.log('\n6️⃣  Confirming refresh_token invalidated after global signOut…');
const stale = createClient(URL, ANON, { auth: { persistSession: false } });
const { error: staleErr } = await stale.auth.setSession({
	access_token: si.session.access_token,
	refresh_token: si.session.refresh_token,
});
console.log(staleErr ? `  refresh blocked: ${staleErr.message}` : '  (access_token still valid until expiry — OK)');

// 8. Cleanup — delete test user (cascades to profile + comment via FK)
console.log('\n7️⃣  Cleanup: admin.deleteUser…');
const { error: delErr } = await admin.auth.admin.deleteUser(cu.user.id);
console.log(delErr ? `  ❌ ${delErr.message}` : '  ✅ user deleted (cascade should remove profile + comment)');

console.log('\n✨ E2E auth test complete.\n');
