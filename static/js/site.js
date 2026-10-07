(() => {
  const nav = document.querySelector('.site-header .nav');
  const toggle = nav?.querySelector('.nav-toggle');
  const links = nav?.querySelector('.nav-links');
  if (toggle && links) {
    nav.classList.add('nav-enhanced');
    const close = () => {
      links.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    };
    toggle.addEventListener('click', () => {
      const open = links.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    nav.addEventListener('keydown', event => {
      if (event.key === 'Escape' && links.classList.contains('is-open')) {
        close();
        toggle.focus();
      }
    });
    links.addEventListener('click', event => { if (event.target.closest('a')) close(); });
  }
  const viewer = document.querySelector('.photo-viewer');
  if (viewer && typeof viewer.showModal === 'function') {
    const image = viewer.querySelector('img');
    const caption = viewer.querySelector('figcaption');
    document.querySelectorAll('[data-gallery-photo]').forEach(link => {
      link.addEventListener('click', event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        image.src = link.href;
        image.alt = link.querySelector('img').alt;
        caption.textContent = link.dataset.caption || image.alt;
        viewer.showModal();
      });
    });
    viewer.querySelector('.photo-viewer-close').addEventListener('click', () => viewer.close());
    viewer.addEventListener('click', event => { if (event.target === viewer) viewer.close(); });
  }
})();
