/**
 * Remove a duplicated leading Markdown H1 from blog posts.
 *
 * BlogPost.astro already renders the frontmatter title as the canonical <h1>.
 * The draft pipeline historically also emits the same title as the first
 * Markdown heading, creating two H1s per article. We strip only the first
 * top-level heading in src/content/blog markdown files at render time so we
 * avoid a noisy 100+ file content rewrite and keep non-blog markdown intact.
 */
export default function stripLeadingBlogH1() {
	return (tree, file) => {
		const path = String(file?.path || file?.history?.[0] || '');
		if (!path.includes('/src/content/blog/')) return;
		if (!Array.isArray(tree.children)) return;

		const firstContentIndex = tree.children.findIndex((node) =>
			node && node.type !== 'yaml' && node.type !== 'toml'
		);
		if (firstContentIndex === -1) return;

		const first = tree.children[firstContentIndex];
		if (first?.type === 'heading' && first.depth === 1) {
			tree.children.splice(firstContentIndex, 1);
		}
	};
}
