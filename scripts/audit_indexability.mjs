#!/usr/bin/env node
/**
 * Build-time SEO guard for Migukstory.
 *
 * Verifies that URLs advertised in dist/sitemap-*.xml are actually indexable:
 * - no utility/private paths in sitemap
 * - no <meta name="robots" content="noindex..."> on sitemap URLs
 * - no dist/_headers X-Robots-Tag: noindex for broad public routes
 */
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const dist = new URL('../dist/', import.meta.url);
const fail = (msg) => {
  console.error(`❌ ${msg}`);
  process.exitCode = 1;
};

if (!existsSync(dist)) {
  fail('dist/ does not exist. Run npm run build first.');
  process.exit();
}

const indexPath = join(dist.pathname, 'sitemap-index.xml');
const sitemapIndex = readFileSync(indexPath, 'utf8');
const sitemapFiles = [...sitemapIndex.matchAll(/<loc>https:\/\/migukstory\.com\/(sitemap-[^<]+)<\/loc>/g)].map((m) => m[1]);
let urls = [];
for (const file of sitemapFiles) {
  const xml = readFileSync(join(dist.pathname, file), 'utf8');
  urls.push(...[...xml.matchAll(/<loc>(https:\/\/migukstory\.com\/[^<]+)<\/loc>/g)].map((m) => m[1]));
}
urls = [...new Set(urls)];
console.log(`Checking ${urls.length} sitemap URLs for accidental noindex...`);

const utilityPath = /^\/(admin|auth|api|login)(\/|$)|^\/404\/?$/;
for (const url of urls) {
  const pathname = new URL(url).pathname;
  if (utilityPath.test(pathname)) {
    fail(`Utility/private URL leaked into sitemap: ${url}`);
    continue;
  }

  let htmlPath = join(dist.pathname, pathname, 'index.html');
  if (pathname === '/') htmlPath = join(dist.pathname, 'index.html');
  if (!existsSync(htmlPath)) continue; // non-HTML/static endpoints are fine

  const html = readFileSync(htmlPath, 'utf8');
  const robotsTags = [...html.matchAll(/<meta\s+[^>]*name=["']robots["'][^>]*>/gi)].map((m) => m[0]);
  const noindex = robotsTags.filter((tag) => /content=["'][^"']*noindex/i.test(tag));
  if (noindex.length) {
    fail(`Sitemap URL has noindex robots meta: ${url} :: ${noindex.join(' ')}`);
  }
}

const headersPath = join(dist.pathname, '_headers');
if (existsSync(headersPath)) {
  const headers = readFileSync(headersPath, 'utf8');
  const broadNoindex = headers.match(/^\/\*[^\n]*(?:\n\s+[^\n]*)*X-Robots-Tag:\s*.*noindex/im);
  if (broadNoindex) fail('Broad /* X-Robots-Tag noindex found in dist/_headers');
}

if (process.exitCode) process.exit(process.exitCode);
console.log('✅ Sitemap URLs are indexable; utility noindex pages are not advertised.');
