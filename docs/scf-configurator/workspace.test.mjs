import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { installWorkspace, renderWorkspaceStatus, restoreCoreTab } from "./workspace.js";

// Small DOM boundary for the workspace controller; configuration parsing and
// generation are exercised by the existing editor contract tests.
function workspace() {
  const node = (dataset = {}) => ({
    dataset, hidden: false, style: {}, attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    focus() { this.focused = true; },
    addEventListener() {},
    closest(selector) { return selector === '[data-core-tab]' && this.dataset.coreTab ? this : null; }
  });
  const tabs = ["overview", "limits", "performance", "abilities", "docking"].map((coreTab) => node({ coreTab }));
  const panels = tabs.map((tab) => node({ corePanel: tab.dataset.coreTab }));
  const pages = ["coreProfiles", "sharedCoreCaps", "exportPage"].map((id) => ({ ...node({ title: id }), id }));
  const counts = ["cores", "groups", "caps", "upgrades"].map((count) => node({ count }));
  const links = pages.map((page) => ({ ...node(), hash: `#${page.id}` }));
  const ids = Object.fromEntries(["workspaceValidation", "workspaceValidationDetail", "navValidationDot", "themeToggle", "currentPageLabel", "mainContent"].map((id) => [id, node()]));
  const listeners = {};
  const selectors = { '[data-core-tab]': tabs, '[data-core-panel]': panels, '.workspace-page': pages, '.nav-link': links, '[data-count]': counts };
  const doc = {
    documentElement: node(),
    querySelectorAll: (selector) => selectors[selector] || [],
    getElementById: (id) => ids[id],
    addEventListener: (name, handler) => { listeners[name] = handler; },
    defaultView: {
      location: { hash: "#sharedCoreCaps" },
      localStorage: { getItem: () => null },
      addEventListener() {}, scrollTo() {}, history: { pushState() {} }
    }
  };
  return { doc, tabs, panels, pages, counts, links, ids, listeners };
}

test("core tab changes keep one panel visible and fall back safely for No Core", () => {
  const w = workspace();
  installWorkspace(w.doc);
  w.listeners.click({ target: w.tabs[4] });
  assert.equal(w.tabs[4].attributes["aria-selected"], "true");
  assert.equal(w.tabs[4].tabIndex, 0);
  assert.deepEqual(w.panels.filter((panel) => !panel.hidden).map((panel) => panel.dataset.corePanel), ["docking"]);

  // Rerendering preserves the active tab; the No Core profile has no docking tab.
  restoreCoreTab(w.doc);
  assert.equal(w.panels[4].hidden, false);
  w.tabs.pop();
  w.panels.pop();
  restoreCoreTab(w.doc);
  assert.equal(w.tabs[0].attributes["aria-selected"], "true");
  assert.deepEqual(w.panels.filter((panel) => !panel.hidden).map((panel) => panel.dataset.corePanel), ["overview"]);
});

test("tabs support keyboard navigation and pages honor the initial URL", () => {
  const w = workspace();
  installWorkspace(w.doc);
  restoreCoreTab(w.doc);
  assert.deepEqual(w.pages.filter((page) => !page.hidden).map((page) => page.id), ["sharedCoreCaps"]);
  assert.equal(w.links[1].attributes["aria-current"], "page");
  let prevented = false;
  w.listeners.keydown({ target: w.tabs[0], key: "End", preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(w.tabs[4].focused, true);
  assert.equal(w.tabs[4].attributes["aria-selected"], "true");
  w.listeners.keydown({ target: w.tabs[4], key: "ArrowRight", preventDefault() {} });
  assert.equal(w.tabs[0].attributes["aria-selected"], "true");
});

test("workspace counts and validation reflect the current configuration", () => {
  const w = workspace();
  const state = { shipCores: [{}, {}], blockGroups: [{}], manifestGroups: [], upgradeModules: [{}, {}, {}] };
  renderWorkspaceStatus(state, { errors: [], warnings: [] }, w.doc);
  assert.deepEqual(w.counts.map((node) => node.textContent), [2, 1, 0, 3]);
  assert.equal(w.ids.workspaceValidation.textContent, "Ready");
  renderWorkspaceStatus(state, { errors: ["Missing subtype"], warnings: [] }, w.doc);
  assert.equal(w.ids.workspaceValidation.textContent, "Needs attention");
  assert.equal(w.ids.workspaceValidationDetail.textContent, "1 error · 0 warnings");
  assert.equal(w.ids.navValidationDot.style.background, "var(--error)");
});

test("connector priority has one editor and no independent manifest-core selector", () => {
  const app = readFileSync(new URL("./app.js", import.meta.url), "utf8");
  assert.equal([...app.matchAll(/<input\b[^>]*data-action="core-selection-priority"/g)].length, 1);
  assert.doesNotMatch(app, /selectedManifestCoreEntryIndex|selected-manifest-core-entry|manifest-core-toggle/);
});
