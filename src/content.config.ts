import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// Topic categories — matches conventions of koreadaily / koreatimes / atlantajoongang
export const CATEGORIES = {
	'immigration': { label: '이민·비자',       slug: 'immigration', color: '#B91C1C' },
	'tax':         { label: '세금·재테크',     slug: 'tax',         color: '#1E40AF' },
	'economy':     { label: '경제·산업',       slug: 'economy',     color: '#0F766E' },
	'ai':          { label: 'AI·자동화',       slug: 'ai',          color: '#6D28D9' },
	'robotics':    { label: '로봇·미래직업',   slug: 'robotics',    color: '#C2410C' },
	'health':      { label: '건강·보험',       slug: 'health',      color: '#047857' },
	'education':   { label: '교육·자녀',       slug: 'education',   color: '#7C3AED' },
	'retirement':  { label: '노후·상속·요양',   slug: 'retirement',  color: '#B7791F' },
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
			draft: z.boolean().default(false),
			heroImage: z.optional(image()),
			tags: z.array(z.string()).default([]),
			category: z.enum([
				'immigration', 'tax', 'economy', 'ai', 'robotics', 'health',
				'education', 'retirement', 'community', 'real-estate',
			]),
			ageGroup: z.enum(['20-35', '35-55', '55+', 'all']).default('all'),
			// Homepage editorial controls. Narrow/local items can remain published but must not
			// automatically become the main headline just because they are newest.
			scope: z.enum(['national', 'regional', 'local']).optional(),
			headlineStrength: z.number().int().min(1).max(5).optional(),
			featured: z.boolean().default(false),
			leadEligible: z.boolean().optional(),
			// E-E-A-T: per-article author slug. Looked up in AUTHORS map in consts.ts.
			// Defaults to 'editorial-staff' (Organization-flavored author) for legacy posts.
			author: z.string().default('editorial-staff'),
			// Optional: legacy field retained so older posts that still carry it in
			// frontmatter validate cleanly. Not rendered anywhere.
			aiAssisted: z.boolean().optional(),
			// Editor's note: a short Korean paragraph (50-150 chars typical) shown at the
			// top of the article body, above the main prose — the named editor's local
			// Korean-American framing for the piece.
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
