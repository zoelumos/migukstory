import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// Topic categories — matches conventions of koreadaily / koreatimes / atlantajoongang
export const CATEGORIES = {
	'immigration': { label: '이민·비자',       slug: 'immigration', color: '#B91C1C' },
	'tax':         { label: '세금·재테크',     slug: 'tax',         color: '#1E40AF' },
	'economy':     { label: '경제·산업',       slug: 'economy',     color: '#0F766E' },
	'health':      { label: '건강·보험',       slug: 'health',      color: '#047857' },
	'education':   { label: '교육·자녀',       slug: 'education',   color: '#7C3AED' },
	'retirement':  { label: '은퇴·연금',       slug: 'retirement',  color: '#B7791F' },
	'community':   { label: '한인 커뮤니티',   slug: 'community',   color: '#0E7490' },
	'real-estate': { label: '부동산·주거',     slug: 'real-estate', color: '#9A3412' },
} as const;

export type CategoryKey = keyof typeof CATEGORIES;

const blog = defineCollection({
	loader: glob({ base: './src/content/blog', pattern: '**/*.{md,mdx}' }),
	schema: ({ image }) =>
		z.object({
			title: z.string(),
			description: z.string(),
			pubDate: z.coerce.date(),
			updatedDate: z.coerce.date().optional(),
			heroImage: z.optional(image()),
			tags: z.array(z.string()).default([]),
			category: z.enum([
				'immigration', 'tax', 'economy', 'health', 'education',
				'retirement', 'community', 'real-estate',
			]),
			ageGroup: z.enum(['20-35', '35-55', '55+', 'all']).default('all'),
			// E-E-A-T: per-article author slug. Looked up in AUTHORS map in consts.ts.
			// Defaults to 'editorial-staff' (Organization-flavored author) for legacy posts.
			author: z.string().default('editorial-staff'),
			// AI-disclosure: when true, post renders a Korean disclosure block at end-of-body.
			// Set on posts that were AI-drafted then human-reviewed.
			aiAssisted: z.boolean().default(false),
			// Editor's note: a short Korean paragraph (50-150 chars typical) shown at the top
			// of the article body, above the main prose. Required E-E-A-T signal for AI-assisted
			// posts — provides the named editor's local KA-angle framing.
			editorNote: z.string().optional(),
			// Optional structured-data fields. Posts that include `faq` will emit
			// FAQPage JSON-LD; `howTo` emits HowTo JSON-LD. Both improve AI/search citability.
			faq: z.array(z.object({
				q: z.string(),
				a: z.string(),
			})).optional(),
			howTo: z.object({
				name: z.string(),
				totalTime: z.string().optional(), // ISO 8601, e.g., "PT30D" = 30 days
				steps: z.array(z.object({
					name: z.string(),
					text: z.string(),
				})),
			}).optional(),
		}),
});

export const collections = { blog };
