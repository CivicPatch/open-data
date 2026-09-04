import { escapeHtml } from "./utils.js";

const STORAGE_KEY = "queryHistory";
const MAX_ENTRIES = 50;

// Tracks queries the user has actually run, persisted to localStorage so it
// survives a reload. Most-recent-first, de-duplicated (re-running the same
// query moves it to the top rather than adding a second entry).
export const History = {
  el: document.getElementById("history-list"),

  load() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch {
      return [];
    }
  },

  add(sql) {
    const trimmed = sql.trim();
    if (!trimmed) return;
    const entries = this.load().filter((s) => s !== trimmed);
    entries.unshift(trimmed);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  },

  render(onSelect) {
    const entries = this.load();
    if (!entries.length) {
      this.el.innerHTML = "<p class='hint'>No queries run yet.</p>";
      return;
    }

    this.el.innerHTML = entries
      .map((sql, i) => `<pre class="history-item" data-index="${i}">${escapeHtml(sql)}</pre>`)
      .join("");

    this.el.querySelectorAll(".history-item").forEach((el) => {
      el.addEventListener("click", () => onSelect(entries[Number(el.dataset.index)]));
    });
  },
};
