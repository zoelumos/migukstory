#!/usr/bin/env node
/**
 * Send newly published Miguk Story posts to newsletter subscribers.
 *
 * Intentionally dependency-free for GitHub Actions. Requires:
 * - SUPABASE_URL or PUBLIC_SUPABASE_URL
 * - SUPABASE_SERVICE_ROLE_KEY
 * - RESEND_API_KEY
 * - NEWSLETTER_FROM, e.g. "미국 스토리 <news@migukstory.com>"
 *
 * If secrets are missing, exits 0 and logs a skip so deploys never fail.
 */
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const SITE_URL = (process.env.SITE_URL || 'https://migukstory.com').replace(/\/$/, '');
const SUPABASE_URL = (process.env.SUPABASE_URL || process.env.PUBLIC_SUPABASE_URL || '').replace(/\/$/, '');
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || '';
const RESEND_API_KEY = process.env.RESEND_API_KEY || '';
const FROM = process.env.NEWSLETTER_FROM || '';
const BASE = process.env.NEWSLETTER_BASE_SHA || process.env.GITHUB_EVENT_BEFORE || '';
const HEAD = process.env.NEWSLETTER_HEAD_SHA || process.env.GITHUB_SHA || 'HEAD';
const DRY_RUN = process.env.NEWSLETTER_DRY_RUN === '1' || process.argv.includes('--dry-run');
const LIMIT = Number(process.env.NEWSLETTER_LIMIT || '200');

function log(...args) { console.log('[newsletter]', ...args); }
function warn(...args) { console.warn('[newsletter]', ...args); }

function shell(args) {
  return execFileSync(args[0], args.slice(1), { encoding: 'utf8' }).trim();
}

function changedBlogFiles() {
  let range = '';
  if (BASE && BASE !== '0000000000000000000000000000000000000000') range = `${BASE}..${HEAD}`;
  else range = `${HEAD}^..${HEAD}`;
  let out = '';
  try {
    out = shell(['git', 'diff', '--name-status', range, '--', 'src/content/blog']);
  } catch (error) {
    warn('could not diff range', range, error?.message || error);
    return [];
  }
  const files = [];
  for (const line of out.split('\n').filter(Boolean)) {
    const [status, ...rest] = line.split(/\t+/);
    const file = rest.at(-1);
    if (!file || !file.endsWith('.md')) continue;
    if (status.startsWith('D')) continue;
    if (fs.existsSync(file)) files.push(file);
  }
  return [...new Set(files)];
}

function parseFrontmatter(raw) {
  if (!raw.startsWith('---')) return { data: {}, body: raw };
  const end = raw.indexOf('\n---', 3);
  if (end === -1) return { data: {}, body: raw };
  const fm = raw.slice(3, end).trim();
  const body = raw.slice(end + 4).trim();
  const data = {};
  for (const line of fm.split('\n')) {
    const m = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (!m) continue;
    let value = m[2].trim();
    if ((value.startsWith("'") && value.endsWith("'")) || (value.startsWith('"') && value.endsWith('"'))) value = value.slice(1, -1);
    if (value === 'true') data[m[1]] = true;
    else if (value === 'false') data[m[1]] = false;
    else data[m[1]] = value;
  }
  return { data, body };
}

function postFromFile(file) {
  const raw = fs.readFileSync(file, 'utf8');
  const { data, body } = parseFrontmatter(raw);
  if (data.draft === true) return null;
  const slug = path.basename(file, '.md');
  const title = String(data.title || body.match(/^#\s+(.+)$/m)?.[1] || slug).trim();
  const description = String(data.description || body.replace(/[#>*_`\-\|]/g, ' ').replace(/\s+/g, ' ').slice(0, 180)).trim();
  return { slug, title, description, url: `${SITE_URL}/blog/${slug}/` };
}

async function supabaseFetch(endpoint, init = {}) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${endpoint}`, {
    ...init,
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
      ...(init.headers || {}),
    },
  });
  const text = await res.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!res.ok) {
    const message = `Supabase ${res.status}: ${typeof body === 'string' ? body : JSON.stringify(body)}`;
    const error = new Error(message);
    error.status = res.status;
    error.body = body;
    error.code = body?.code || null;
    throw error;
  }
  return body;
}

function isMissingTableError(error, table) {
  const haystack = `${error?.code || ''} ${error?.message || ''} ${JSON.stringify(error?.body || {})}`;
  return haystack.includes('PGRST205') && haystack.includes(table);
}

async function getSubscribers() {
  return await supabaseFetch('subscribers?select=id,email&unsubscribed_at=is.null&order=created_at.desc');
}

async function alreadySent(email, slug) {
  const q = `newsletter_sends?select=id&email=eq.${encodeURIComponent(email)}&post_slug=eq.${encodeURIComponent(slug)}&limit=1`;
  try {
    const rows = await supabaseFetch(q);
    return Array.isArray(rows) && rows.length > 0;
  } catch (error) {
    if (isMissingTableError(error, 'newsletter_sends')) {
      warn('newsletter_sends table missing; skipping duplicate-send ledger check until migration 008 is applied');
      return false;
    }
    throw error;
  }
}

async function recordSend(subscriber, post, status, providerId = null, error = null) {
  try {
    await supabaseFetch('newsletter_sends', {
      method: 'POST',
      headers: { Prefer: 'resolution=ignore-duplicates,return=minimal' },
      body: JSON.stringify({
        subscriber_id: subscriber.id,
        email: subscriber.email,
        post_slug: post.slug,
        post_title: post.title,
        provider: 'resend',
        provider_id: providerId,
        status,
        error: error ? String(error).slice(0, 500) : null,
        metadata: { url: post.url, ci: process.env.GITHUB_RUN_ID || null },
      }),
    });
  } catch (e) {
    warn('failed to record send ledger for', subscriber.email, post.slug, e?.message || e);
  }
}

function emailHtml(post) {
  return `
  <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.6;color:#1f1a17;max-width:640px;margin:0 auto;padding:24px">
    <p style="font-size:13px;color:#8a5a44;margin:0 0 10px">미국 스토리 새 글 알림</p>
    <h1 style="font-size:24px;line-height:1.25;margin:0 0 14px">${escapeHtml(post.title)}</h1>
    <p style="font-size:16px;color:#4b403a;margin:0 0 22px">${escapeHtml(post.description)}</p>
    <p><a href="${post.url}" style="display:inline-block;background:#8b3f2f;color:white;text-decoration:none;padding:12px 18px;border-radius:6px;font-weight:700">글 읽기</a></p>
    <hr style="border:none;border-top:1px solid #eee;margin:28px 0">
    <p style="font-size:12px;color:#777">회원가입 또는 뉴스레터 구독으로 받은 메일입니다. 수신 해지는 이 메일에 답장해 주세요.</p>
  </div>`;
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function sendEmail(to, post) {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: FROM,
      to,
      subject: `미국 스토리 새 글: ${post.title}`.slice(0, 180),
      html: emailHtml(post),
      text: `미국 스토리 새 글\n\n${post.title}\n\n${post.description}\n\n${post.url}\n\n수신 해지는 이 메일에 답장해 주세요.`,
    }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`Resend ${res.status}: ${JSON.stringify(body)}`);
  return body.id || null;
}

async function main() {
  const files = changedBlogFiles();
  const posts = files.map(postFromFile).filter(Boolean);
  log('changed posts', posts.map((p) => p.slug).join(', ') || '(none)');
  if (posts.length === 0) return;

  if (!SUPABASE_URL || !SERVICE_KEY || !RESEND_API_KEY || !FROM) {
    log('skip: missing SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY/RESEND_API_KEY/NEWSLETTER_FROM');
    return;
  }

  const subscribers = await getSubscribers();
  log('subscribers', subscribers.length);
  let sent = 0;
  for (const post of posts) {
    for (const subscriber of subscribers) {
      if (LIMIT && sent >= LIMIT) { log('limit reached', LIMIT); return; }
      if (!subscriber.email || await alreadySent(subscriber.email, post.slug)) continue;
      if (DRY_RUN) { log('dry-run would send', subscriber.email, post.slug); continue; }
      try {
        const id = await sendEmail(subscriber.email, post);
        await recordSend(subscriber, post, 'sent', id, null);
        sent += 1;
      } catch (e) {
        warn('send failed', subscriber.email, post.slug, e?.message || e);
        await recordSend(subscriber, post, 'error', null, e?.message || e);
      }
    }
  }
  log('sent', sent);
}

main().catch((error) => {
  console.error('[newsletter] fatal', error);
  process.exit(1);
});
