export function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[ch]);
}

export function formatCell(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "bigint") return value.toString();
  return String(value);
}
