#!/usr/bin/env node
/**
 * Build-time SEO guard for Migukstory.
 *
 * Verifies that URLs advertised in dist/sitemap-*.xml are actually indexable:
 * - no utility/private paths in sitemap
 * - no <meta name="robots" content="noindex..."> on sitemap URLs
 * - no dist/_headers X-Robots-Tag: noindex for broad public routes
 */
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
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

const htmlFiles = [];
const walkHtml = (dir) => {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const stat = statSync(path);
    if (stat.isDirectory()) walkHtml(path);
    else if (entry.endsWith('.html')) htmlFiles.push(path);
  }
};
walkHtml(dist.pathname);

const canonicalUtilityPath = /^\/(?:login|admin|admin\/enroll-mfa|auth\/callback)\/$/;
for (const file of htmlFiles) {
  const rel = `/${file.slice(dist.pathname.length).replace(/index\.html$/, '').replace(/\\/g, '/')}`;
  const pathname = rel === '//' ? '/' : rel;
  const html = readFileSync(file, 'utf8');

  if (canonicalUtilityPath.test(pathname) || pathname === '/404/') {
    const robotsTags = [...html.matchAll(/<meta\s+[^>]*name=["']robots["'][^>]*>/gi)].map((m) => m[0]);
    if (!robotsTags.some((tag) => /content=["'][^"']*noindex/i.test(tag))) {
      fail(`Utility/private page missing noindex robots meta: ${pathname}`);
    }
  }

  const anchors = [...html.matchAll(/<a\s+[^>]*href=["'](\/(?:login|admin|auth(?:\/|$))(?:["'?#][^>]*)?)[^>]*>/gi)].map((m) => m[0]);
  for (const anchor of anchors) {
    const href = anchor.match(/href=["']([^"']+)/i)?.[1] || '';
    const bareUtility = /^\/(?:login|admin|auth\/callback)(?:[?#].*)?$/.test(href);
    if (bareUtility) fail(`Internal utility link uses redirecting non-canonical URL in ${pathname}: ${anchor}`);
    if (!/rel=["'][^"']*nofollow/i.test(anchor)) fail(`Internal utility link missing rel=\"nofollow\" in ${pathname}: ${anchor}`);
  }
}

if (process.exitCode) process.exit(process.exitCode);
console.log('✅ Sitemap URLs are indexable; utility noindex pages are not advertised or linked as redirect targets.');
