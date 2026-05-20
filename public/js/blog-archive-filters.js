(() => {
  const archive = document.getElementById('archive');
  if (!archive) return;

  const items = Array.from(archive.querySelectorAll('.archive-item'));
  const visibleCount = document.getElementById('visible-count');
  const emptyMsg = document.getElementById('empty-msg');
  const sortSelect = document.getElementById('sort-select');
  const searchInput = document.getElementById('search-input');

  if (!visibleCount || !emptyMsg || !sortSelect || !searchInput) return;

  let activeCat = 'all';
  let activeTag = 'all';

  function applyFilters() {
    const q = searchInput.value.trim().toLowerCase();
    let visible = 0;

    items.forEach((it) => {
      const cat = it.dataset.cat || '';
      const tags = (it.dataset.tags || '').split('|').filter(Boolean);
      const title = it.dataset.title || '';
      const desc = it.dataset.desc || '';
      let show = true;

      if (activeCat !== 'all' && cat !== activeCat) show = false;
      if (activeTag !== 'all' && !tags.includes(activeTag)) show = false;
      if (q && !title.includes(q) && !desc.includes(q) && !tags.some((t) => t.toLowerCase().includes(q))) {
        show = false;
      }

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
    sorted.forEach((it) => archive.appendChild(it));
  }

  document.querySelectorAll('[data-filter-cat]').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-filter-cat]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      activeCat = btn.dataset.filterCat || 'all';
      applyFilters();
    });
  });

  document.querySelectorAll('[data-filter-tag]').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-filter-tag]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      activeTag = btn.dataset.filterTag || 'all';
      applyFilters();
    });
  });

  sortSelect.addEventListener('change', applySort);
  searchInput.addEventListener('input', applyFilters);

  const url = new URL(window.location.href);
  const initCat = url.searchParams.get('category');
  const initTag = url.searchParams.get('tag');
  const initQ = url.searchParams.get('q');

  if (initCat) {
    const btn = document.querySelector(`[data-filter-cat="${CSS.escape(initCat)}"]`);
    if (btn) btn.click();
  }
  if (initTag) {
    const btn = document.querySelector(`[data-filter-tag="${CSS.escape(initTag)}"]`);
    if (btn) btn.click();
  }
  if (initQ) {
    searchInput.value = initQ;
    applyFilters();
  }
})();
