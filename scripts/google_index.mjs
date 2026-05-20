#!/usr/bin/env node
/**
 * Google indexing automation for migukstory.com.
 *
 * Auth: service account. Locally reads .secrets/gsc-service-account.json;
 * in CI reads the JSON from the GSC_SERVICE_ACCOUNT_JSON env var.
 *
 * Commands:
 *   node scripts/google_index.mjs auth     — verify service-account access
 *   node scripts/google_index.mjs sitemap  — submit sitemap to Search Console
 *   node scripts/google_index.mjs status   — index-status report for all URLs
 *   node scripts/google_index.mjs push     — Indexing API push for all URLs
 *   node scripts/google_index.mjs all      — sitemap + push (the CI default)
 *
 * Property is a Domain property: sc-domain:migukstory.com
 */
import { createSign } from 'node:crypto';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repo = resolve(__dirname, '..');

// Load service account — env var (CI) takes precedence over local file
let SA;
if (process.env.GSC_SERVICE_ACCOUNT_JSON) {
	SA = JSON.parse(process.env.GSC_SERVICE_ACCOUNT_JSON);
} else {
	const localPath = join(repo, '.secrets/gsc-service-account.json');
	if (!existsSync(localPath)) {
		console.error('No service account: set GSC_SERVICE_ACCOUNT_JSON or add .secrets/gsc-service-account.json');
		process.exit(1);
	}
	SA = JSON.parse(readFileSync(localPath, 'utf8'));
}

// Domain property in Search Console
const SITE = 'sc-domain:migukstory.com';
const SITEMAP = 'https://migukstory.com/sitemap-index.xml';

const b64url = (s) =>
	Buffer.from(s).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

function makeJWT(scope) {
	const now = Math.floor(Date.now() / 1000);
	const header = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
	const claims = b64url(
		JSON.stringify({
			iss: SA.client_email,
			scope,
			aud: 'https://oauth2.googleapis.com/token',
			iat: now,
			exp: now + 3600,
		})
	);
	const signer = createSign('RSA-SHA256');
	signer.update(`${header}.${claims}`);
	const sig = signer
		.sign(SA.private_key)
		.toString('base64')
		.replace(/\+/g, '-')
		.replace(/\//g, '_')
		.replace(/=+$/, '');
	return `${header}.${claims}.${sig}`;
}

async function getToken(scope) {
	const r = await fetch('https://oauth2.googleapis.com/token', {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({
			grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
			assertion: makeJWT(scope),
		}),
	});
	const j = await r.json();
	if (!j.access_token) throw new Error('token error: ' + JSON.stringify(j));
	return j.access_token;
}

async function getSitemapUrls() {
	const idx = await (await fetch(SITEMAP)).text();
	const subs = Array.from(idx.matchAll(/<loc>([^<]+)<\/loc>/g)).map((m) => m[1]);
	const all = [];
	for (const sm of subs) {
		const x = await (await fetch(sm)).text();
		all.push(...Array.from(x.matchAll(/<loc>([^<]+)<\/loc>/g)).map((m) => m[1]));
	}
	// Skip auth/admin/api routes — no SEO value, shouldn't be indexed
	return [...new Set(all)].filter(
		(u) => !/\/(api|admin|login|auth)(\/|$)/.test(new URL(u).pathname)
	);
}

async function cmdAuth() {
	const tok = await getToken('https://www.googleapis.com/auth/webmasters.readonly');
	const r = await fetch('https://searchconsole.googleapis.com/webmasters/v3/sites', {
		headers: { Authorization: `Bearer ${tok}` },
	});
	const j = await r.json();
	if (!j.siteEntry || !j.siteEntry.length) {
		console.log('⚠️  Service account sees NO sites.');
		console.log('   Add', SA.client_email, 'as an Owner of', SITE);
		process.exit(2);
	}
	console.log('Sites visible to service account:');
	j.siteEntry.forEach((s) => console.log(`  ${s.siteUrl}  [${s.permissionLevel}]`));
}

async function cmdSitemap() {
	const tok = await getToken('https://www.googleapis.com/auth/webmasters');
	const r = await fetch(
		`https://searchconsole.googleapis.com/webmasters/v3/sites/${encodeURIComponent(SITE)}/sitemaps/${encodeURIComponent(SITEMAP)}`,
		{ method: 'PUT', headers: { Authorization: `Bearer ${tok}` } }
	);
	console.log('Sitemap submit:', r.status, r.ok ? '✅' : await r.text());
}

async function cmdStatus() {
	const tok = await getToken('https://www.googleapis.com/auth/webmasters.readonly');
	const urls = await getSitemapUrls();
	console.log(`Inspecting ${urls.length} URLs...`);
	const buckets = {};
	for (const url of urls) {
		try {
			const r = await fetch('https://searchconsole.googleapis.com/v1/urlInspection/index:inspect', {
				method: 'POST',
				headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
				body: JSON.stringify({ inspectionUrl: url, siteUrl: SITE }),
			});
			const j = await r.json();
			const cov = j?.inspectionResult?.indexStatusResult?.coverageState || j.error?.message || '?';
			(buckets[cov] = buckets[cov] || []).push(url);
		} catch (e) {
			(buckets['ERROR'] = buckets['ERROR'] || []).push(url + ' — ' + e.message);
		}
		await new Promise((r) => setTimeout(r, 300));
	}
	for (const [state, list] of Object.entries(buckets)) {
		console.log(`\n${state} (${list.length}):`);
		list.forEach((u) => console.log('  ' + u));
	}
}

async function cmdPush() {
	const tok = await getToken('https://www.googleapis.com/auth/indexing');
	const urls = await getSitemapUrls();
	console.log(`Pushing ${urls.length} URLs via Indexing API...`);
	let ok = 0, fail = 0;
	for (const url of urls) {
		const r = await fetch('https://indexing.googleapis.com/v3/urlNotifications:publish', {
			method: 'POST',
			headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
			body: JSON.stringify({ url, type: 'URL_UPDATED' }),
		});
		if (r.ok) ok++;
		else { fail++; console.log(`  ✗ ${url} — ${r.status} ${(await r.text()).slice(0, 100)}`); }
		await new Promise((r) => setTimeout(r, 200));
	}
	console.log(`\n✅ ${ok} pushed, ${fail} failed.`);
	if (fail > 0) process.exitCode = 1;
}

const cmd = process.argv[2] || 'auth';
const fns = { auth: cmdAuth, sitemap: cmdSitemap, status: cmdStatus, push: cmdPush };
if (cmd === 'all') {
	await cmdSitemap();
	await cmdPush();
} else if (fns[cmd]) {
	await fns[cmd]();
} else {
	console.log('Unknown command. Use: auth | sitemap | status | push | all');
	process.exit(1);
}
