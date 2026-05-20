(() => {
  const list = document.getElementById('cat-list');
  if (!list) return;

  const items = Array.from(list.querySelectorAll('.archive-item'));
  const visibleCount = document.getElementById('visible-count');
  const sortSelect = document.getElementById('sort-select');
  const searchInput = document.getElementById('search-input');
  const emptyMsg = document.getElementById('empty-filter');

  if (!visibleCount || !sortSelect || !searchInput || !emptyMsg) return;

  function applyFilter() {
    const q = searchInput.value.trim().toLowerCase();
    let visible = 0;

    items.forEach((it) => {
      const title = it.dataset.title || '';
      const desc = it.dataset.desc || '';
      const tags = (it.dataset.tags || '').toLowerCase();
      const show = !q || title.includes(q) || desc.includes(q) || tags.includes(q);
      it.style.display = show ? '' : 'none';
      if (show) visible += 1;
    });

    visibleCount.textContent = String(visible);
    emptyMsg.hidden = visible !== 0;
  }

  function applySort() {
    const mode = sortSelect.value;
    const sorted = [...items].sort((a, b) => {
      const aDate = a.dataset.date || '';
      const bDate = b.dataset.date || '';
      const aTitle = a.dataset.title || '';
      const bTitle = b.dataset.title || '';
      if (mode === 'newest') return bDate.localeCompare(aDate);
      if (mode === 'oldest') return aDate.localeCompare(bDate);
      if (mode === 'title') return aTitle.localeCompare(bTitle, 'ko');
      return 0;
    });
    sorted.forEach((it) => list.appendChild(it));
  }

  searchInput.addEventListener('input', applyFilter);
  sortSelect.addEventListener('change', applySort);
})();
