(() => {
  const configuration = document.querySelector('#contact-modes');
  const form = document.querySelector('.contact-form');
  if (!configuration || !form) return;
  const modes = JSON.parse(configuration.textContent);
  const tabs = [...document.querySelectorAll('[data-contact-mode]')];
  const apply = (kind, updateUrl = true) => {
    const mode = modes[kind];
    if (!mode) return;
    form.elements.kind.value = kind;
    document.querySelectorAll('[data-contact-copy]').forEach(element => {
      element.textContent = mode[element.dataset.contactCopy];
    });
    document.querySelectorAll('[data-contact-label]').forEach(element => {
      element.textContent = mode.labels[element.dataset.contactLabel];
    });
    Object.entries(mode.placeholders).forEach(([name, placeholder]) => {
      form.elements[name].placeholder = placeholder;
    });
    tabs.forEach(tab => {
      const selected = tab.dataset.contactMode === kind;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected) tab.setAttribute('aria-current', 'page');
      else tab.removeAttribute('aria-current');
    });
    if (updateUrl) {
      const url = new URL(tabs.find(tab => tab.dataset.contactMode === kind).href);
      url.hash = '';
      history.replaceState(null, '', url);
    }
  };
  const tabList = document.querySelector('.contact-tabs');
  tabList.setAttribute('role', 'tablist');
  const panel = document.querySelector('.contact-card-inner');
  panel.id = 'contact-panel';
  panel.setAttribute('role', 'tabpanel');
  tabs.forEach((tab, index) => {
    tab.id = `contact-tab-${tab.dataset.contactMode.toLowerCase()}`;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', panel.id);
    tab.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      apply(tab.dataset.contactMode);
      panel.setAttribute('aria-labelledby', tab.id);
    });
    tab.addEventListener('keydown', event => {
      let target;
      if (event.key === 'ArrowRight') target = tabs[(index + 1) % tabs.length];
      if (event.key === 'ArrowLeft') target = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === 'Home') target = tabs[0];
      if (event.key === 'End') target = tabs[tabs.length - 1];
      if (event.key === ' ' || event.key === 'Enter') target = tab;
      if (!target) return;
      event.preventDefault();
      target.click();
      target.focus();
    });
  });
  const initial = form.elements.kind.value;
  if (modes[initial]) {
    apply(initial, false);
    panel.setAttribute('aria-labelledby', tabs.find(tab => tab.dataset.contactMode === initial).id);
  }
})();
