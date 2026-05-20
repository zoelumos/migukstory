(() => {
  // Mobile hamburger toggle — accessible (aria-expanded), closes on Escape + outside click.
  // Served as an external same-origin file because the production CSP blocks inline
  // scripts (script-src 'self' …, no 'unsafe-inline'). Loaded with `defer` so the
  // DOM is parsed before this runs.
  const masthead = document.querySelector('.masthead');
  const toggle = masthead && masthead.querySelector('.nav-toggle');
  const nav = masthead && masthead.querySelector('#primary-nav');
  if (!toggle || !nav || !masthead) return;

  const setOpen = (open) => {
    masthead.classList.toggle('nav-open', open);
    document.documentElement.classList.toggle('nav-drawer-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
  };

  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    setOpen(toggle.getAttribute('aria-expanded') !== 'true');
  });
  nav.addEventListener('click', (e) => {
    if (e.target.closest('a')) setOpen(false);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') setOpen(false);
  });
  document.addEventListener('click', (e) => {
    if (!masthead.contains(e.target)) setOpen(false);
  });
})();
