#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const envText = readFileSync(join(resolve(__dirname, '..'), '.env'), 'utf8');
const env = Object.fromEntries(
	envText.split('\n').filter((l) => l && !l.startsWith('#') && l.includes('='))
		.map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
);

const ref = env.SUPABASE_PROJECT_REF;
const tok = env.SUPABASE_ACCESS_TOKEN;

const run = async (sql) => {
	const r = await fetch(`https://api.supabase.com/v1/projects/${ref}/database/query`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${tok}` },
		body: JSON.stringify({ query: sql }),
	});
	return { status: r.status, body: await r.text() };
};

// 1. Verify table exists + check RLS + indexes
const checks = await run(`
  select
    (select count(*) from pg_tables where schemaname='public' and tablename='subscribers') as table_exists,
    (select rowsecurity from pg_tables where schemaname='public' and tablename='subscribers') as rls_on,
    (select count(*) from pg_indexes where schemaname='public' and tablename='subscribers') as index_count,
    (select count(*) from pg_policies where schemaname='public' and tablename='subscribers') as policy_count;
`);
console.log('Schema check:', checks.body);

// 2. Verify columns
const cols = await run(`
  select column_name, data_type, is_nullable, column_default
  from information_schema.columns
  where table_schema='public' and table_name='subscribers'
  order by ordinal_position;
`);
console.log('\nColumns:', cols.body);

// 3. Count rows (should be 0 initially)
const cnt = await run(`select count(*) as rows from public.subscribers;`);
console.log('\nRows:', cnt.body);
