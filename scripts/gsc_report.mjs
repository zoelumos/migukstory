#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import crypto from 'node:crypto';

const SITE = process.env.SITE_URL || 'https://migukstory.com/';
const SITEMAP = new URL('/sitemap-index.xml', SITE).toString();

function loadServiceAccount() {
  if (process.env.GSC_SERVICE_ACCOUNT) {
    const raw = Buffer.from(process.env.GSC_SERVICE_ACCOUNT, 'base64').toString('utf8');
    return JSON.parse(raw);
  }
  if (process.env.GSC_SERVICE_ACCOUNT_JSON) return JSON.parse(process.env.GSC_SERVICE_ACCOUNT_JSON);
  const local = join(process.cwd(), '.secrets', 'gsc-service-account.json');
  if (existsSync(local)) return JSON.parse(readFileSync(local, 'utf8'));
  throw new Error('Missing GSC_SERVICE_ACCOUNT or local .secrets/gsc-service-account.json');
}

const SA = loadServiceAccount();

function b64url(input) {
  return Buffer.from(input).toString('base64url');
}

async function getToken(scope) {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: 'RS256', typ: 'JWT' };
  const claim = {
    iss: SA.client_email,
    scope,
    aud: 'https://oauth2.googleapis.com/token',
    exp: now + 3600,
    iat: now,
  };
  const unsigned = `${b64url(JSON.stringify(header))}.${b64url(JSON.stringify(claim))}`;
  const sig = crypto.createSign('RSA-SHA256').update(unsigned).sign(SA.private_key);
  const assertion = `${unsigned}.${Buffer.from(sig).toString('base64url')}`;
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion }),
  });
  const j = await r.json();
  if (!j.access_token) throw new Error(`token error: ${JSON.stringify(j)}`);
  return j.access_token;
}

function isoDate(daysAgo) {
  const d = new Date(Date.now() - daysAgo * 86400_000);
  return d.toISOString().slice(0, 10);
}

async function getSitemapUrls() {
  const idx = await (await fetch(SITEMAP)).text();
  const subs = Array.from(idx.matchAll(/<loc>([^<]+)<\/loc>/g)).map((m) => m[1]);
  const urls = [];
  for (const sm of subs) {
    const xml = await (await fetch(sm)).text();
    urls.push(...Array.from(xml.matchAll(/<loc>([^<]+)<\/loc>/g)).map((m) => m[1]));
  }
  return [...new Set(urls)].filter((u) => !/\/(api|admin|login|auth)(\/|$)/.test(new URL(u).pathname));
}

async function listSites(tok) {
  const r = await fetch('https://searchconsole.googleapis.com/webmasters/v3/sites', {
    headers: { Authorization: `Bearer ${tok}` },
  });
  const j = await r.json();
  return j.siteEntry || [];
}

async function searchAnalytics(tok, days, dimensions, rowLimit = 10) {
  const startDate = isoDate(days);
  const endDate = isoDate(2); // Search Console data usually lags 1-2 days.
  const r = await fetch(`https://searchconsole.googleapis.com/webmasters/v3/sites/${encodeURIComponent(SITE)}/searchAnalytics/query`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ startDate, endDate, dimensions, rowLimit, startRow: 0 }),
  });
  const j = await r.json();
  if (!r.ok) return { error: j.error?.message || JSON.stringify(j), startDate, endDate, rows: [] };
  return { startDate, endDate, rows: j.rows || [] };
}

async function inspectUrl(tok, url) {
  const r = await fetch('https://searchconsole.googleapis.com/v1/urlInspection/index:inspect', {
    method: 'POST',
    headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ inspectionUrl: url, siteUrl: SITE }),
  });
  const j = await r.json();
  if (!r.ok) return { url, error: j.error?.message || JSON.stringify(j) };
  const s = j.inspectionResult?.indexStatusResult || {};
  return {
    url,
    verdict: s.verdict || '',
    coverageState: s.coverageState || '',
    indexingState: s.indexingState || '',
    pageFetchState: s.pageFetchState || '',
    robotsTxtState: s.robotsTxtState || '',
    lastCrawlTime: s.lastCrawlTime || '',
    googleCanonical: s.googleCanonical || '',
    userCanonical: s.userCanonical || '',
  };
}

function printRows(title, report) {
  console.log(`\n## ${title} (${report.startDate} → ${report.endDate})`);
  if (report.error) {
    console.log(`ERROR: ${report.error}`);
    return;
  }
  if (!report.rows.length) {
    console.log('NO_ROWS');
    return;
  }
  let clicks = 0, impressions = 0;
  for (const row of report.rows) {
    clicks += row.clicks || 0;
    impressions += row.impressions || 0;
  }
  console.log(`top_rows=${report.rows.length} top_rows_clicks=${clicks} top_rows_impressions=${impressions}`);
  for (const row of report.rows.slice(0, 10)) {
    const key = (row.keys || []).join(' | ');
    console.log(`${row.clicks || 0}\t${row.impressions || 0}\tctr=${((row.ctr || 0) * 100).toFixed(2)}%\tpos=${(row.position || 0).toFixed(1)}\t${key}`);
  }
}

const tok = await getToken('https://www.googleapis.com/auth/webmasters.readonly');
console.log(`# GSC report for ${SITE}`);
console.log(`service_account=${SA.client_email}`);

const sites = await listSites(tok);
console.log('\n## Sites visible');
for (const s of sites) console.log(`${s.siteUrl}\t${s.permissionLevel}`);
if (!sites.some((s) => s.siteUrl === SITE || s.siteUrl === SITE.replace(/\/$/, ''))) {
  console.log(`WARNING: Exact property ${SITE} was not listed. Queries may fail if property mismatch exists.`);
}

printRows('Performance by page - last 28 days', await searchAnalytics(tok, 28, ['page'], 20));
printRows('Performance by query - last 28 days', await searchAnalytics(tok, 28, ['query'], 20));
printRows('Performance by page - last 7 days', await searchAnalytics(tok, 7, ['page'], 10));

const sitemapUrls = await getSitemapUrls();
console.log(`\n## Sitemap URL count\n${sitemapUrls.length}`);
const preferred = [
  new URL('/', SITE).toString(),
  new URL('/blog/', SITE).toString(),
  new URL('/topics/', SITE).toString(),
  new URL('/first-30-days/', SITE).toString(),
];
const sample = [...new Set([...preferred, ...sitemapUrls.filter((u) => /\/blog\//.test(new URL(u).pathname)).slice(0, 8)])].slice(0, 12);
console.log('\n## URL Inspection sample');
const buckets = new Map();
for (const url of sample) {
  const r = await inspectUrl(tok, url);
  const state = r.error || r.coverageState || r.verdict || 'UNKNOWN';
  buckets.set(state, (buckets.get(state) || 0) + 1);
  console.log(JSON.stringify(r));
  await new Promise((resolve) => setTimeout(resolve, 250));
}
console.log('\n## URL Inspection buckets');
for (const [state, count] of buckets) console.log(`${state}\t${count}`);
