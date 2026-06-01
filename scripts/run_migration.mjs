#!/usr/bin/env node
/**
 * One-shot migration runner — reads .env, posts SQL to Supabase Management API.
 *
 * Usage: node scripts/run_migration.mjs migrations/001_subscribers.sql
 */

import { readFileSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repo = resolve(__dirname, '..');

// Load .env when present (no dotenv dep — simple parser), then let real
// environment variables override it. This keeps local one-shot use working but
// also allows GitHub Actions / shell-secret runs where committing .env is not
// acceptable.
let fileEnv = {};
try {
	const envText = readFileSync(join(repo, '.env'), 'utf8');
	fileEnv = Object.fromEntries(
		envText
			.split('\n')
			.filter((l) => l && !l.startsWith('#') && l.includes('='))
			.map((l) => {
				const idx = l.indexOf('=');
				return [l.slice(0, idx).trim(), l.slice(idx + 1).trim()];
			})
	);
} catch (error) {
	if (error?.code !== 'ENOENT') throw error;
}
const env = { ...fileEnv, ...process.env };

const TOKEN = env.SUPABASE_ACCESS_TOKEN;
const REF = env.SUPABASE_PROJECT_REF;

if (!TOKEN || !REF) {
	console.error('Missing SUPABASE_ACCESS_TOKEN or SUPABASE_PROJECT_REF in .env');
	process.exit(1);
}

const migrationPath = process.argv[2];
if (!migrationPath) {
	console.error('Usage: node scripts/run_migration.mjs <path-to-sql>');
	process.exit(1);
}

const sql = readFileSync(resolve(repo, migrationPath), 'utf8');
console.log(`📜 Running ${migrationPath} (${sql.length} chars) on project ${REF}...\n`);

const res = await fetch(`https://api.supabase.com/v1/projects/${REF}/database/query`, {
	method: 'POST',
	headers: {
		'Content-Type': 'application/json',
		'Authorization': `Bearer ${TOKEN}`,
	},
	body: JSON.stringify({ query: sql }),
});

const body = await res.text();
console.log(`HTTP ${res.status}`);
console.log(body.slice(0, 1500));

if (!res.ok) process.exit(1);
console.log('\n✅ Migration applied.');
