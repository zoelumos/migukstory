type BlogLike = {
	id: string;
	data: {
		title: string;
		description?: string;
		category?: string;
		pubDate: Date;
		tags?: string[];
		scope?: 'national' | 'regional' | 'local';
		headlineStrength?: number;
		featured?: boolean;
		leadEligible?: boolean;
		[key: string]: unknown;
	};
};

type Scope = 'national' | 'regional' | 'local';

const HIGH_STAKES_TERMS = [
	'uscis', '비자', '영주권', 'i-485', 'i-130', 'h-1b', 'h1b', 'f-1', 'opt', 'ice', '추방', '망명',
	'green card', 'visa bulletin', 'citizenship', 'naturalization', '이민', '시민권',
	'irs', '세금', 'tax', 'fbar', 'salt', 'fafsa', 'medicare', '보험', 'health', 'social security', 'ssa',
	'금리', '모기지', 'mortgage', '주택', '학자금', 'college', '은퇴', '연금', '401k',
	'대법원', 'scotus', 'trump', '연방', 'deadline', '마감', '주의', '변경', 'cutoff', 'fee', 'increase',
	'war', '전쟁', 'gaza', 'ukraine', 'north korea', '북핵', 'taiwan', '대만', '미중', '한미',
];

const NARROW_LOCAL_TERMS = [
	'tennessee', '테네시', 'carrollton', 'newark', 'atlanta', 'dallas', 'houston', 'chicago', 'los angeles',
	'warehouse', 'factory', 'sorting facility', 'plant', 'county', 'local police', 'restaurant', 'shrimpers',
	'level 1 exercise normal precautions', 'level 2 exercise increased caution', 'travel advisory',
];

const CATEGORY_WEIGHT: Record<string, number> = {
	'immigration': 90,
	'tax': 75,
	'health': 65,
	'education': 60,
	'retirement': 58,
	'real-estate': 52,
	'economy': 48,
	'community': 25,
	'ai': 30,
	'robotics': 18,
};

function textFor(post: BlogLike) {
	return [post.data.title, post.data.description, ...(post.data.tags || [])]
		.join(' ')
		.toLowerCase();
}

function hasAny(text: string, terms: string[]) {
	return terms.some(term => text.includes(term));
}

export function inferHeadlineScope(post: BlogLike): Scope {
	if (post.data.scope) return post.data.scope;

	const text = textFor(post);
	const highStakes = hasAny(text, HIGH_STAKES_TERMS);
	const narrowLocal = hasAny(text, NARROW_LOCAL_TERMS);

	if (narrowLocal) return 'local';
	if (post.data.category === 'community' && !highStakes) return 'regional';
	return 'national';
}

export function inferHeadlineStrength(post: BlogLike): number {
	if (typeof post.data.headlineStrength === 'number') {
		return Math.max(1, Math.min(5, post.data.headlineStrength));
	}

	const text = textFor(post);
	let strength = 2;
	if (hasAny(text, HIGH_STAKES_TERMS)) strength += 2;
	if (/\b(2026|2027|\$|\d+%|\d+만|\d+천|\d+일|deadline|마감|변경|인상|중단|위험|주의|체크리스트)\b/i.test(text)) strength += 1;
	if (post.data.category === 'immigration' || post.data.category === 'tax') strength += 1;
	if (inferHeadlineScope(post) === 'local') strength -= 2;

	return Math.max(1, Math.min(5, strength));
}

export function isLeadEligible(post: BlogLike) {
	if (post.data.leadEligible === false) return false;
	const scope = inferHeadlineScope(post);
	const strength = inferHeadlineStrength(post);
	return scope !== 'local' && strength >= 4;
}

export function headlinePriorityScore(post: BlogLike) {
	const scope = inferHeadlineScope(post);
	const strength = inferHeadlineStrength(post);
	const categoryWeight = CATEGORY_WEIGHT[post.data.category || ''] || 0;
	const featuredBoost = post.data.featured || post.data.leadEligible === true ? 300 : 0;
	const scopeBoost = scope === 'national' ? 80 : scope === 'regional' ? 20 : -250;
	const localPenalty = scope === 'local' ? -500 : 0;

	return featuredBoost + strength * 100 + categoryWeight + scopeBoost + localPenalty;
}

export function compareForHomepage(a: BlogLike, b: BlogLike) {
	const scoreDiff = headlinePriorityScore(b) - headlinePriorityScore(a);
	if (scoreDiff !== 0) return scoreDiff;
	return b.data.pubDate.valueOf() - a.data.pubDate.valueOf();
}

export function splitHomepageStories<T extends BlogLike>(posts: T[]) {
	const latest = [...posts].sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
	const eligible = latest.filter(isLeadEligible).sort(compareForHomepage);
	const lead = eligible[0] || latest.find(post => inferHeadlineScope(post) !== 'local');
	const rest = latest.filter(post => post.id !== lead?.id).sort(compareForHomepage);
	const eligibleAboveFold = rest.filter(isLeadEligible);
	const nonLocalFallback = rest.filter(post => inferHeadlineScope(post) !== 'local' && !eligibleAboveFold.includes(post));

	return {
		lead,
		aboveFold: [...eligibleAboveFold, ...nonLocalFallback].slice(0, 2),
		continued: rest,
	};
}
