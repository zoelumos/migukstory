/**
 * Build-time safety net: convert any ```mermaid code block into a static,
 * mobile-readable Markdown list so a fragile/broken diagram can never ship.
 *
 * Why this exists
 * ---------------
 * The drafting pipeline forbids Mermaid (draft_from_rss / improve_drafts /
 * editor_grade / publish_from_queue all reject it), and live diagrams were
 * hand-converted to mobile summaries. But the Hermes "editor 통과" auto-publish
 * path commits posts straight to src/content/blog, bypassing the deterministic
 * publish gate — which is exactly how a handful of ```mermaid blocks slipped
 * back onto the site. Client-side Mermaid rendering (CDN + JS) is also invisible
 * to search/AI crawlers and shifts layout.
 *
 * So instead of relying on every upstream gate, we transform at the LAST place
 * everything funnels through: the build. Every `npm run build` (including the
 * daily-post pre-push check and the Cloudflare deploy build) runs this, so no
 * matter how a Mermaid block reached the content, the rendered page shows a
 * clean list rather than raw code or a broken/empty diagram.
 *
 * It is deliberately a *fallback*, not the primary authoring path: linear
 * flows become an ordered list; decision trees become a "조건 → 결과" bullet
 * list; unrecognized diagram types degrade to a plain list of their text
 * labels. Never raw code.
 */

const ARROW = /-\.->|--+>|==+>|--+|-\.-/;
// Matches one arrow occurrence plus an optional |edge label| that follows it.
const ARROW_WITH_LABEL = /(-\.->|--+>|==+>|--+|-\.-)\s*(?:\|\s*"?([^|]*?)"?\s*\|)?/;
// Lines that are pure Mermaid styling/structure, not content.
const NOISE = /^(flowchart|graph|style|classDef|class|linkStyle|click|subgraph|end|direction|%%)\b/i;

function cleanLabel(raw) {
	if (raw == null) return '';
	return String(raw)
		.replace(/<br\s*\/?>/gi, ' / ')
		.replace(/\\n/g, ' / ')
		.replace(/&quot;/g, '"')
		.replace(/^["'`]+|["'`]+$/g, '')
		.replace(/\s*\/\s*/g, ' / ')
		.replace(/\s+/g, ' ')
		.trim();
}

// Pull "id" and optional bracketed label out of a node token like
// A["x"], B{x}, C(x), D[[x]], E((x)). Registers the label if present.
function readNode(token, labels, order) {
	token = token.trim();
	const m = token.match(/^([A-Za-z0-9_]+)\s*(?:(\[\[|\(\(|\{\{|\[\/|\[|\(|\{)([\s\S]*?)(\]\]|\)\)|\}\}|\/\]|\]|\)|\}))?/);
	if (!m) return null;
	const id = m[1];
	if (!(id in labels)) {
		labels[id] = null;
		order.push(id);
	}
	if (m[3] != null && m[3].trim() !== '') {
		labels[id] = cleanLabel(m[3]);
	}
	return id;
}

function parseFlowchart(src) {
	const labels = {};
	const order = [];
	const edges = [];
	const lines = src.split('\n').map((l) => l.trim()).filter(Boolean);

	for (const line of lines) {
		if (NOISE.test(line)) continue;
		if (ARROW.test(line)) {
			// Split a possibly-chained edge line (A --> B --> C) into node tokens,
			// capturing any |label| that sits on each arrow.
			const segs = [];
			const edgeLabels = [];
			let working = line;
			let mm;
			while ((mm = working.match(ARROW_WITH_LABEL)) && mm.index !== undefined) {
				segs.push(working.slice(0, mm.index));
				edgeLabels.push(mm[2] ? cleanLabel(mm[2]) : null);
				working = working.slice(mm.index + mm[0].length);
			}
			segs.push(working);
			const ids = segs.map((s) => readNode(s, labels, order)).filter(Boolean);
			for (let i = 0; i + 1 < ids.length; i++) {
				edges.push({ from: ids[i], to: ids[i + 1], label: edgeLabels[i] || null });
			}
		} else {
			readNode(line, labels, order);
		}
	}

	const labelOf = (id) => labels[id] || id;
	return { labels, order, edges, labelOf };
}

// mdast helpers
const text = (value) => ({ type: 'text', value });
const strong = (value) => ({ type: 'strong', children: [text(value)] });
function listItem(children) {
	return { type: 'listItem', spread: false, children: [{ type: 'paragraph', children }] };
}
function list(ordered, items) {
	return { type: 'list', ordered, spread: false, children: items };
}

function renderFlowchart(src) {
	const { order, edges, labelOf } = parseFlowchart(src);
	if (!order.length) return null;

	const outdeg = {};
	const indeg = {};
	for (const id of order) {
		outdeg[id] = 0;
		indeg[id] = 0;
	}
	for (const e of edges) {
		outdeg[e.from] = (outdeg[e.from] || 0) + 1;
		indeg[e.to] = (indeg[e.to] || 0) + 1;
	}

	const branching = edges.some((e) => e.label) || order.some((id) => outdeg[id] > 1);

	// Pure linear chain → ordered list of labels in flow order.
	if (!branching && edges.length) {
		const start = order.find((id) => indeg[id] === 0) || order[0];
		const seen = new Set();
		const seq = [];
		let cur = start;
		while (cur && !seen.has(cur)) {
			seen.add(cur);
			seq.push(cur);
			const next = edges.find((e) => e.from === cur);
			cur = next ? next.to : null;
		}
		for (const id of order) if (!seen.has(id)) seq.push(id);
		return list(true, seq.map((id) => listItem([text(labelOf(id))])));
	}

	// Otherwise → "출발 → (조건) 도착" bullet list, one per edge.
	if (edges.length) {
		const items = edges.map((e) => {
			const children = [strong(labelOf(e.from)), text(' → ')];
			if (e.label) children.push(text(`(${e.label}) `));
			children.push(text(labelOf(e.to)));
			return listItem(children);
		});
		return list(false, items);
	}

	// Nodes but no edges → plain bullet list of labels.
	return list(false, order.map((id) => listItem([text(labelOf(id))])));
}

// Last-resort renderer for non-flowchart diagrams (mindmap, gantt, etc.):
// list the human-readable text lines, never raw syntax.
function renderGeneric(src) {
	const extractLabel = (l) => {
		let s = l.replace(/^[-*>|]+/, '').trim();
		// id((label)) / id[label] / id{label} / ((label)) → keep inner label
		const m = s.match(/^[A-Za-z0-9_]*\s*(?:\[\[|\(\(|\{\{|\[|\(|\{)([\s\S]*?)(?:\]\]|\)\)|\}\}|\]|\)|\})\s*$/);
		if (m) s = m[1];
		else s = s.replace(/^[A-Za-z0-9_]+\s*[:>]\s*/, '');
		return cleanLabel(s);
	};
	const lines = src
		.split('\n')
		.map((l) => l.trim())
		.filter((l) => l && !NOISE.test(l) && !/^(mindmap|gantt|sequenceDiagram|pie|gitGraph|erDiagram|journey|timeline|stateDiagram)/i.test(l))
		.map(extractLabel)
		.filter(Boolean);
	if (!lines.length) return null;
	return list(false, lines.map((l) => listItem([text(l)])));
}

function convert(src) {
	const firstLine = src.split('\n').map((l) => l.trim()).find(Boolean) || '';
	if (/^(flowchart|graph)\b/i.test(firstLine)) {
		return renderFlowchart(src) || renderGeneric(src);
	}
	return renderGeneric(src);
}

export default function remarkMermaidMobile() {
	return (tree) => {
		const walk = (node) => {
			if (!node || !Array.isArray(node.children)) return;
			for (let i = 0; i < node.children.length; i++) {
				const child = node.children[i];
				if (child && child.type === 'code' && child.lang === 'mermaid') {
					const replacement = convert(child.value || '');
					if (replacement) {
						node.children.splice(i, 1, replacement);
						continue; // replacement has no mermaid children to recurse into
					}
				}
				walk(child);
			}
		};
		walk(tree);
	};
}
