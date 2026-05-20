/**
 * Auto-generated article table of contents (목차).
 *
 * Served as an external same-origin script: the site CSP (see public/_headers)
 * drops 'unsafe-inline' from script-src/script-src-elem, so inline <script>
 * blocks are blocked by the browser. Loaded with `defer`, so the article DOM
 * is fully parsed before this runs.
 *
 * Scans the .prose container for H2/H3 headings, assigns stable id anchors,
 * builds the nested list, and wires active-section highlighting on scroll.
 */
(() => {
  const prose = document.querySelector('.prose');
  const list = document.getElementById('toc-list');
  const wrap = document.getElementById('article-toc');
  if (!prose || !list || !wrap) return;

  const heads = prose.querySelectorAll('h2, h3');
  if (heads.length < 3) {
    wrap.style.display = 'none';
    return;
  }

  heads.forEach((h, i) => {
    if (!h.id) {
      h.id = 'sec-' + (i + 1) + '-' + (h.textContent || '')
        .toLowerCase()
        .replace(/[^a-z0-9가-힣]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 40);
    }
    const li = document.createElement('li');
    li.className = h.tagName === 'H3' ? 'lvl-3' : 'lvl-2';
    const a = document.createElement('a');
    a.href = '#' + h.id;
    a.textContent = h.textContent || '';
    li.appendChild(a);
    list.appendChild(li);
  });

  // Active-section highlighting on scroll
  const links = list.querySelectorAll('a');
  const ioMap = {};
  links.forEach((a) => {
    ioMap[a.getAttribute('href').slice(1)] = a;
  });
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      const a = ioMap[entry.target.id];
      if (!a) return;
      if (entry.isIntersecting) {
        links.forEach((l) => l.classList.remove('active'));
        a.classList.add('active');
      }
    });
  }, { rootMargin: '-20% 0% -70% 0%' });
  heads.forEach((h) => io.observe(h));

  // Collapse the TOC on small screens by default
  if (window.matchMedia('(max-width: 720px)').matches) {
    wrap.open = false;
  }
})();
