// @ts-check
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

// Architecture: 100% static Astro build → Cloudflare Pages.
// Auth endpoints live in /functions/ (Cloudflare Pages Functions) and auto-deploy
// alongside the static site via wrangler pages deploy.
//
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
				const url = new URL(page);
				const path = url.pathname;
				return !(
					path.startsWith('/admin/') ||
					path === '/admin/' ||
					path.startsWith('/auth/') ||
					path === '/login/'
				);
			},
		}),
	],
	markdown: {
		shikiConfig: { theme: 'github-light', wrap: true },
	},
});
