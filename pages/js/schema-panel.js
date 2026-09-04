import { escapeHtml } from "./utils.js";

// Buckets a DuckDB column type (e.g. "DECIMAL(18,3)", "TIMESTAMP WITH TIME ZONE")
// into one of a few badge categories for at-a-glance readability.
function typeCategory(type) {
  const t = type.toUpperCase();
  if (/^(BOOLEAN|BOOL)/.test(t)) return "boolean";
  if (/^(DATE|TIME|TIMESTAMP|INTERVAL)/.test(t)) return "date";
  if (/^(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT|UTINYINT|USMALLINT|UINTEGER|UBIGINT|UHUGEINT|DOUBLE|FLOAT|DECIMAL|NUMERIC|REAL)/.test(t)) {
    return "number";
  }
  if (/^(VARCHAR|TEXT|CHAR|STRING|UUID|BLOB)/.test(t)) return "text";
  return "other";
}

// Lists registered tables + columns, both sourced from manifest.json —
// column name/type is computed once at export time (src/utils/parquet.py's
// describe_columns) rather than queried live via information_schema, which
// would mean touching every partition file's Parquet footer over the
// network (60+ files across all tables) just to learn column names that
// never change between exports. Rendered in two places: a compact,
// clickable name list near the top (renderNames), and the full column/type
// reference in the Definitions modal (renderDefinitions).
export const SchemaPanel = {
  namesEl: document.getElementById("table-names-wrap"),
  definitionsEl: document.getElementById("table-definitions-wrap"),

  // Only needs table names + row counts (both already free from the
  // manifest) — deliberately does NOT depend on load()'s information_schema
  // query, so the pills can render immediately without waiting on schema
  // resolution across every registered table (57 files for master_ocdids).
  renderNames(tableNames, rowCounts, onSelectTable) {
    if (!tableNames.length) {
      this.namesEl.innerHTML = "";
      return;
    }

    const pillsHtml = tableNames
      .map((table) => {
        const rows = rowCounts.get(table);
        const rowsLabel = rows === undefined ? "" : ` (${rows.toLocaleString()})`;
        return `<button type="button" class="table-pill" data-table="${escapeHtml(table)}">${escapeHtml(table)}${escapeHtml(rowsLabel)}</button>`;
      })
      .join("");

    this.namesEl.innerHTML = `<h2>Tables</h2><div class="table-pills">${pillsHtml}</div>`;

    this.namesEl.querySelectorAll(".table-pill").forEach((btn) => {
      btn.addEventListener("click", () => onSelectTable(btn.dataset.table));
    });
  },

  // manifestTables: the manifest.json "tables" entries for whichever tables
  // actually got registered as views (each has name/rows/columns already —
  // no DB query involved).
  renderDefinitions(manifestTables) {
    if (!manifestTables.length) {
      this.definitionsEl.innerHTML = "";
      return;
    }

    const tablesHtml = manifestTables
      .map((t) => {
        const colsHtml = (t.columns || [])
          .map((c) => {
            const category = typeCategory(c.type);
            return `${escapeHtml(c.name)} <span class="type-badge type-badge--${category}">${escapeHtml(c.type)}</span>`;
          })
          .join(", ");
        const rowCountHtml = t.rows === undefined
          ? ""
          : `<div class="schema-row-count">${t.rows.toLocaleString()} row${t.rows === 1 ? "" : "s"}</div>`;
        return `
          <div class="schema-table">
            <div class="def-table-name">${escapeHtml(t.name)}</div>
            ${rowCountHtml}
            <div class="schema-columns">${colsHtml}</div>
          </div>
        `;
      })
      .join("");

    this.definitionsEl.innerHTML = tablesHtml;
  },
};
