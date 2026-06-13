// Remembers which category groups are collapsed, persisting per-category state
// in localStorage so it survives HTMX search/filter swaps and page reloads.
(function () {
  "use strict";

  var STORAGE_KEY = "parts-collapsed-categories";
  var applying = false; // guard so programmatic open/close doesn't re-trigger saves

  function loadCollapsed() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return new Set(raw ? JSON.parse(raw) : []);
    } catch (e) {
      return new Set();
    }
  }

  function saveCollapsed(set) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
    } catch (e) {
      /* storage unavailable (private mode / quota) — degrade silently */
    }
  }

  function groups() {
    return document.querySelectorAll("details.category-group[data-group-id]");
  }

  // Apply stored collapsed state to every currently-rendered group.
  function applyState() {
    var collapsed = loadCollapsed();
    applying = true;
    groups().forEach(function (el) {
      el.open = !collapsed.has(el.dataset.groupId);
    });
    applying = false;
    updateButton();
  }

  // Keep storage in sync when the user opens/closes a single group.
  function onToggle(e) {
    var el = e.target;
    if (applying || !el.matches || !el.matches("details.category-group[data-group-id]")) {
      return;
    }
    var collapsed = loadCollapsed();
    if (el.open) {
      collapsed.delete(el.dataset.groupId);
    } else {
      collapsed.add(el.dataset.groupId);
    }
    saveCollapsed(collapsed);
    updateButton();
  }

  function anyOpen() {
    return Array.prototype.some.call(groups(), function (el) {
      return el.open;
    });
  }

  // Toggle button collapses all visible groups, or expands them if all collapsed.
  function onButtonClick() {
    var collapse = anyOpen();
    var collapsed = loadCollapsed();
    applying = true;
    groups().forEach(function (el) {
      el.open = !collapse;
      if (collapse) {
        collapsed.add(el.dataset.groupId);
      } else {
        collapsed.delete(el.dataset.groupId);
      }
    });
    applying = false;
    saveCollapsed(collapsed);
    updateButton();
  }

  function updateButton() {
    var btn = document.getElementById("collapse-all");
    if (!btn) return;
    btn.textContent = anyOpen() ? "Collapse all" : "Expand all";
  }

  function init() {
    var btn = document.getElementById("collapse-all");
    if (btn) btn.addEventListener("click", onButtonClick);
    // `toggle` does not bubble, so listen in the capture phase.
    document.addEventListener("toggle", onToggle, true);
    // Re-apply after HTMX swaps the parts table back in (htmx events bubble).
    document.addEventListener("htmx:afterSwap", applyState);
    applyState();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
