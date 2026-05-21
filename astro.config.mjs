// @ts-check
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

// Architecture: 100% static Astro build → Cloudflare Pages.
// Auth endpoints live in /functions/ (Cloudflare Pages Functions) and auto-deploy
// alongside the static site via wrangler pages deploy.

// ── Per-page lastmod map ────────────────────────────────────────────────────
// Google only honors <lastmod> when it's "consistently and verifiably accurate"
// — a uniform build-timestamp across every URL gets the attribute discounted.
// So we build a real per-URL date map from blog frontmatter (updatedDate, else
// pubDate) and only emit lastmod for those URLs. Non-blog pages get no lastmod
// rather than a fake one.
const blogDir = fileURLToPath(new URL('./src/content/blog/', import.meta.url));
/** @type {Record<string, string>} */
const lastmodByUrl = {};
try {
	for (const file of readdirSync(blogDir)) {
		if (!/\.(md|mdx)$/.test(file)) continue;
		const slug = file.replace(/\.(md|mdx)$/, '');
		const raw = readFileSync(blogDir + file, 'utf8');
		const updated = raw.match(/^updatedDate:\s*['"]?(\d{4}-\d{2}-\d{2})/m);
		const pub = raw.match(/^pubDate:\s*['"]?(\d{4}-\d{2}-\d{2})/m);
		const date = (updated && updated[1]) || (pub && pub[1]);
		if (date) lastmodByUrl[`https://migukstory.com/blog/${slug}/`] = date;
	}
} catch {
	/* blog dir missing during some tooling runs — sitemap still builds */
}

// https://astro.build/config
export default defineConfig({
	site: 'https://migukstory.com',
	integrations: [
		mdx(),
		sitemap({
			i18n: { defaultLocale: 'ko', locales: { ko: 'ko-KR' } },
			// Keep crawl budget focused on public editorial/commercial pages.
			// Utility/auth/admin URLs should not be advertised in the sitemap.
			filter: (page) => {
				const path = new URL(page).pathname;
				return !(
					path.startsWith('/admin/') ||
					path === '/admin/' ||
					path.startsWith('/auth/') ||
					path === '/login/' ||
					path === '/404/'
				);
			},
			// Accurate per-page lastmod from blog frontmatter; omit it entirely
			// for pages without a verifiable date (rather than fake a uniform one).
			serialize: (item) => {
				const real = lastmodByUrl[item.url];
				if (real) item.lastmod = real;
				else delete item.lastmod;
				return item;
			},
		}),
	],
	markdown: {
		shikiConfig: { theme: 'github-light', wrap: true },
	},
});
