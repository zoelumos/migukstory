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

const run = async (q) => {
	const r = await fetch(`https://api.supabase.com/v1/projects/${env.SUPABASE_PROJECT_REF}/database/query`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${env.SUPABASE_ACCESS_TOKEN}` },
		body: JSON.stringify({ query: q }),
	});
	return await r.json();
};

console.log('Policies on subscribers:');
console.log(JSON.stringify(await run(`
  select policyname, permissive, roles, cmd, qual, with_check
  from pg_policies
  where schemaname='public' and tablename='subscribers';
`), null, 2));

console.log('\nGrants on subscribers:');
console.log(JSON.stringify(await run(`
  select grantee, privilege_type
  from information_schema.role_table_grants
  where table_schema='public' and table_name='subscribers'
  order by grantee, privilege_type;
`), null, 2));

console.log('\nGrants on schema public to anon:');
console.log(JSON.stringify(await run(`
  select grantee, privilege_type
  from information_schema.role_usage_grants
  where object_schema='public' and grantee in ('anon','authenticated');
`), null, 2));
