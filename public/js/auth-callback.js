(() => {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const rawNext = params.get('next') || '/';
  const next = rawNext.startsWith('/') && !rawNext.startsWith('//') ? rawNext : '/';
  const msg = document.querySelector('[data-msg]');
  if (msg) msg.textContent = '로그인 경로를 확인하고 있습니다…';

  window.setTimeout(() => {
    window.location.href = `/login/?next=${encodeURIComponent(next)}`;
  }, 800);
})();
