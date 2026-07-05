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
	'irs', '세금', 'tax', 'fbar', 'salt', 'fafsa', 'medicare', 'medicaid', '보험', 'health', 'social security', 'ssa',
	'금리', '모기지', 'mortgage', '주택', '학자금', 'college', '은퇴', '연금', '401k', 'mapt', 'trust', 'elder law', 'estate planning', 'probate', 'nursing home', 'long-term care',
	'대법원', 'scotus', 'trump', '연방', 'deadline', '마감', '주의', '변경', 'cutoff', 'fee', 'increase',
	'scam', 'fraud', 'identity theft', 'data breach', 'consumer protection', 'ftc', 'cfpb', 'recall', '사기', '리콜',
	'war', '전쟁', 'gaza', 'ukraine', 'north korea', '북핵', 'taiwan', '대만', '미중', '한미',
	'iran', '이란', 'israel', '이스라엘', 'hormuz', '호르무즈', 'middle east', '중동',
	'미사일', 'missile', 'airstrike', '공습', '휴전', 'ceasefire', 'drone', '드론',
	'oil', 'crude', '유가', '가스값', 'gas price', 'gasoline', 'travel advisory', '여행경보',
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
	'consumer': 55,
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

function dateKey(post: BlogLike) {
	return post.data.pubDate.toISOString().slice(0, 10);
}

export function splitHomepageStories<T extends BlogLike>(posts: T[]) {
	const latest = [...posts].sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
	const newestDate = latest[0] ? dateKey(latest[0]) : '';
	const todayPosts = latest.filter(post => dateKey(post) === newestDate);
	const olderPosts = latest.filter(post => dateKey(post) !== newestDate);

	// Homepage must behave like a live news front page: whenever fresh posts are
	// published, the headline + above-fold "slides" must come from the newest
	// publication date first. High-scoring older service guides are valuable, but
	// they must never bury today's breaking/current-news package.
	const todayEligible = todayPosts.filter(isLeadEligible).sort(compareForHomepage);
	const todayNonLocal = todayPosts
		.filter(post => inferHeadlineScope(post) !== 'local' && !todayEligible.includes(post))
		.sort(compareForHomepage);
	const olderEligible = olderPosts.filter(isLeadEligible).sort(compareForHomepage);

	const lead = todayEligible[0] || todayNonLocal[0] || olderEligible[0] || olderPosts.find(post => inferHeadlineScope(post) !== 'local');
	const rest = latest.filter(post => post.id !== lead?.id);
	const todayRest = rest.filter(post => dateKey(post) === newestDate);
	const olderRest = rest.filter(post => dateKey(post) !== newestDate);
	const todayAboveFold = todayRest.filter(isLeadEligible).sort(compareForHomepage);
	const todayFallback = todayRest
		.filter(post => inferHeadlineScope(post) !== 'local' && !todayAboveFold.includes(post))
		.sort(compareForHomepage);
	// Above-fold cards are labeled "오늘 꼭 읽어야 할 뉴스", so they must feel
	// current. Fill from the newest publication date first; if still under two
	// cards, keep walking back through older dates until we have 2. Never let
	// the section render with 0 or 1 cards because a single day only had 1 post.
	const aboveFoldPool = [...todayAboveFold, ...todayFallback];
	if (aboveFoldPool.length < 2) {
		const needed = 2 - aboveFoldPool.length;
		const olderFill = olderRest
			.filter(post => inferHeadlineScope(post) !== 'local')
			.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf())
			.slice(0, needed);
		aboveFoldPool.push(...olderFill);
	}
	const aboveFold = aboveFoldPool.slice(0, 2);

	return {
		lead,
		aboveFold,
		// "계속해서 읽기" must be a live-news rail, not another editorial-priority
		// rail. Readers expect the newest published posts first here, even when an
		// older USCIS/tax guide scores higher for headline placement.
		continued: [...todayRest.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()), ...olderRest.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf())],
	};
}
