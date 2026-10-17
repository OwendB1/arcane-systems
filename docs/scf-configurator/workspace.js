let activeCoreTab = 'overview';

export function restoreCoreTab(doc = document) {
  const tabs = [...doc.querySelectorAll('[data-core-tab]')];
  if (!tabs.some((tab) => tab.dataset.coreTab === activeCoreTab)) activeCoreTab = 'overview';
  tabs.forEach((tab) => {
    const active = tab.dataset.coreTab === activeCoreTab;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  doc.querySelectorAll('[data-core-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.corePanel !== activeCoreTab;
  });
}

export function renderWorkspaceStatus(state, validation, doc = document) {
  const counts = { cores: state.shipCores.length, groups: state.blockGroups.length, caps: state.manifestGroups.length, upgrades: state.upgradeModules.length };
  doc.querySelectorAll('[data-count]').forEach((node) => { node.textContent = counts[node.dataset.count]; });
  const errors = validation.errors.length;
  const warnings = validation.warnings.length;
  const status = doc.getElementById('workspaceValidation');
  status.textContent = errors ? 'Needs attention' : warnings ? 'Review' : 'Ready';
  status.style.color = errors ? 'var(--error)' : warnings ? 'var(--warning)' : 'var(--success)';
  doc.getElementById('workspaceValidationDetail').textContent = errors || warnings
    ? `${errors} error${errors === 1 ? '' : 's'} · ${warnings} warning${warnings === 1 ? '' : 's'}` : 'No configuration errors';
  doc.getElementById('navValidationDot').style.background = status.style.color;
}

export function installWorkspace(doc = document) {
  const pages = [...doc.querySelectorAll('.workspace-page')];
  const win = doc.defaultView;
  function showPage(id, focus = false) {
    const page = pages.find((page) => page.id === id) || pages[0];
    pages.forEach((item) => { item.hidden = item !== page; });
    doc.querySelectorAll('.nav-link').forEach((link) => {
      if (link.hash === `#${page.id}`) {
        link.setAttribute('aria-current', 'page');
        link.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
      }
      else link.removeAttribute('aria-current');
    });
    doc.getElementById('currentPageLabel').textContent = page.dataset.title;
    doc.title = `${page.dataset.title} · Arcane Systems`;
    if (focus) {
      doc.getElementById('mainContent').focus({ preventScroll: true });
      win.scrollTo(0, 0);
    }
  }
  doc.addEventListener('click', (event) => {
    const tab = event.target.closest?.('[data-core-tab]');
    if (tab) {
      activeCoreTab = tab.dataset.coreTab;
      restoreCoreTab(doc);
      return;
    }
    const link = event.target.closest?.('a[href^="#"]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const id = link.hash.slice(1);
    if (!pages.some((page) => page.id === id)) return;
    event.preventDefault();
    if (link.dataset.openCoreTab) {
      activeCoreTab = link.dataset.openCoreTab;
      restoreCoreTab(doc);
    }
    win.history.pushState(null, '', link.hash);
    showPage(id, true);
  });
  doc.addEventListener('keydown', (event) => {
    const tab = event.target.closest?.('[data-core-tab]');
    if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabs = [...doc.querySelectorAll('[data-core-tab]')];
    const index = tabs.indexOf(tab);
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
      : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    event.preventDefault();
    activeCoreTab = tabs[nextIndex].dataset.coreTab;
    restoreCoreTab(doc);
    tabs[nextIndex].focus();
  });
  win.addEventListener('popstate', () => showPage(win.location.hash.slice(1), true));
  win.addEventListener('hashchange', () => showPage(win.location.hash.slice(1), true));
  showPage(win.location.hash.slice(1));

  const toggle = doc.getElementById('themeToggle');
  function setTheme(theme) {
    doc.documentElement.dataset.theme = theme;
    toggle.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
  }
  try { setTheme(win.localStorage.getItem('scf-editor-theme') === 'light' ? 'light' : 'dark'); } catch { setTheme('dark'); }
  toggle.addEventListener('click', () => {
    const theme = doc.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(theme);
    try { win.localStorage.setItem('scf-editor-theme', theme); } catch { /* Theme still works when browser storage is unavailable. */ }
  });
}
