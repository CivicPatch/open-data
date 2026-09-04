// Light/dark toggle, persisted to localStorage. The initial value is applied
// synchronously in a small inline script in <head> (before first paint, to
// avoid a flash of the wrong theme) — this module only owns the toggle button.
export const Theme = {
  toggleBtn: document.getElementById("theme-toggle"),

  init() {
    this.toggleBtn.addEventListener("click", () => this.toggle());
  },

  toggle() {
    const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const current = document.documentElement.dataset.theme || (systemPrefersDark ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
  },
};
