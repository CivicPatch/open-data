import { escapeHtml, formatCell } from "./utils.js";
import { History } from "./history.js";

export const PAGE_SIZE = 100;

// Where a paginated query's rows are held between page turns. `row_number()` gives them a total
// order the user's SQL may not have, which is what makes a page a fixed slice rather than
// whichever rows a fresh execution happened to return.
const PAGE_TABLE = "_page_src";

// Owns the SQL box, results table, pagination, and CSV export. Every query
// submitted through run() is paginated by wrapping it as a subquery with
// LIMIT/OFFSET pushed down into DuckDB — this keeps huge result sets (e.g.
// scanning master_ocdids' ~195k rows with no LIMIT) from ever being rendered
// into the DOM at once. CSV export, however, covers every row matching the
// current query (not just the page on screen) — see exportCsv() for how it
// stays non-blocking for large exports.
export const QueryRunner = {
  queryEl: document.getElementById("query"),
  runBtn: document.getElementById("run"),
  exportBtn: document.getElementById("export-csv"),
  resultsWrap: document.getElementById("results-wrap"),
  metaEl: document.getElementById("meta"),
  errorEl: document.getElementById("error"),
  paginationEl: document.getElementById("pagination"),
  prevBtn: document.getElementById("page-prev"),
  nextBtn: document.getElementById("page-next"),
  pageInfoEl: document.getElementById("page-info"),
  conn: null,
  lastResult: null,

  // Pagination state for the query currently on screen. baseSql is the
  // user's SQL with any trailing ";" stripped, ready to be wrapped as a
  // subquery; null means the last query couldn't be paginated (e.g. it
  // wasn't a SELECT) and ran as-is.
  baseSql: null,
  offset: 0,
  totalRows: 0,
  // True while a page turn is in flight. See goToPage.
  paging: false,
  // The page a URL asked for, applied on the next run once the row count is known.
  pendingPage: 1,

  // The query and page live in the URL so a result can be linked, bookmarked, and survive a
  // reload. `replaceState`, not `pushState`: paging is not navigation, and filling the back
  // stack with page turns would make Back mean "one row further up" instead of "leave".
  syncUrl() {
    const params = new URLSearchParams();
    params.set("sql", this.queryEl.value.trim());
    const page = Math.floor(this.offset / PAGE_SIZE) + 1;
    if (page > 1) params.set("page", String(page));
    history.replaceState(null, "", `?${params}`);
  },

  // What the URL asks for, or nothing. The page number is clamped when the query runs, since
  // only then is the row count known — a link to page 900 of a 3-page result should land on
  // the last page rather than an empty one.
  fromUrl() {
    const params = new URLSearchParams(location.search);
    const sql = params.get("sql");
    if (!sql) return null;
    const page = Number(params.get("page") ?? 1);
    return { sql, page: Number.isFinite(page) && page > 0 ? Math.floor(page) : 1 };
  },

  init(conn) {
    this.conn = conn;
    this.runBtn.addEventListener("click", () => this.run());
    this.exportBtn.addEventListener("click", () => this.exportCsv());
    this.prevBtn.addEventListener("click", () => this.goToPage(-1));
    this.nextBtn.addEventListener("click", () => this.goToPage(1));
    this.queryEl.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") this.run();
    });
  },

  setQuery(sql) {
    this.queryEl.value = sql;
  },

  showError(err) {
    this.errorEl.textContent = err instanceof Error ? err.message : String(err);
    this.errorEl.style.display = "block";
  },

  clearError() {
    this.errorEl.style.display = "none";
    this.errorEl.textContent = "";
  },

  renderResults(table) {
    this.lastResult = table;
    const cols = table.schema.fields.map((f) => f.name);
    const rows = table.toArray();

    if (rows.length === 0) {
      this.resultsWrap.innerHTML = "<p class='hint'>Query returned no rows.</p>";
      this.metaEl.textContent = "";
      this.exportBtn.disabled = true;
      // Not an early return. Leaving before this froze both buttons in whatever state the
      // previous page left them, so landing on an empty page stranded the reader with no way
      // forward or back.
      this.updatePaginationUI();
      return;
    }

    const thead = `<thead><tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>`;
    const tbody = `<tbody>${rows
      .map(
        (row) =>
          `<tr>${cols.map((c) => `<td>${escapeHtml(formatCell(row[c]))}</td>`).join("")}</tr>`
      )
      .join("")}</tbody>`;

    this.resultsWrap.innerHTML = `<table>${thead}${tbody}</table>`;
    this.exportBtn.disabled = false;

    if (this.baseSql) {
      const from = this.totalRows === 0 ? 0 : this.offset + 1;
      const to = Math.min(this.offset + rows.length, this.totalRows);
      this.metaEl.textContent = `Rows ${from}–${to} of ${this.totalRows}`;
    } else {
      this.metaEl.textContent = `${rows.length} row${rows.length === 1 ? "" : "s"}`;
    }
    this.updatePaginationUI();
  },

  updatePaginationUI() {
    if (!this.baseSql || this.totalRows <= PAGE_SIZE) {
      this.paginationEl.hidden = true;
      return;
    }
    this.paginationEl.hidden = false;
    const currentPage = Math.floor(this.offset / PAGE_SIZE) + 1;
    const totalPages = Math.ceil(this.totalRows / PAGE_SIZE);
    this.pageInfoEl.textContent = `Page ${currentPage} of ${totalPages}`;
    this.prevBtn.disabled = this.offset <= 0;
    this.nextBtn.disabled = this.offset + PAGE_SIZE >= this.totalRows;
  },

  escapeCsvCell(value) {
    const str = formatCell(value);
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
  },

  toCsv(table) {
    const cols = table.schema.fields.map((f) => f.name);
    const rows = table.toArray();

    const lines = [cols.map((c) => this.escapeCsvCell(c)).join(",")];
    for (const row of rows) {
      lines.push(cols.map((c) => this.escapeCsvCell(row[c])).join(","));
    }
    return lines.join("\r\n");
  },

  downloadBlob(blob) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `query-results-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  async exportCsv() {
    if (!this.baseSql) {
      // Non-paginated fallback path: lastResult already *is* the full result.
      if (!this.lastResult) return;
      this.downloadBlob(new Blob([this.toCsv(this.lastResult)], { type: "text/csv;charset=utf-8;" }));
      return;
    }

    // Exports every row matching the current query, not just the page on
    // screen. Streams Arrow record batches via conn.send() (rather than
    // conn.query(), which would materialize the whole result at once) and
    // yields to the event loop between batches, so a large export (e.g. an
    // unfiltered scan of master_ocdids' ~195k rows) builds the CSV in the
    // background without freezing the tab.
    const originalLabel = this.exportBtn.textContent;
    this.exportBtn.disabled = true;
    this.exportBtn.textContent = "Exporting…";
    this.clearError();

    try {
      // The materialised table, not the user's SQL: the export is then exactly the rows that
      // were paged through, in the same order. Re-running the query could return a different
      // ordering — the same reason paging over it was broken.
      const reader = await this.conn.send(
        `SELECT * EXCLUDE (_row) FROM ${PAGE_TABLE} ORDER BY _row`
      );
      const chunks = [];
      let cols = null;

      for await (const batch of reader) {
        if (!cols) {
          cols = batch.schema.fields.map((f) => f.name);
          chunks.push(cols.map((c) => this.escapeCsvCell(c)).join(",") + "\r\n");
        }
        for (const row of batch.toArray()) {
          chunks.push(cols.map((c) => this.escapeCsvCell(row[c])).join(",") + "\r\n");
        }
        // Yield to the browser between batches so the page stays responsive.
        await new Promise((resolve) => setTimeout(resolve, 0));
      }

      this.downloadBlob(new Blob(chunks, { type: "text/csv;charset=utf-8;" }));
    } catch (err) {
      this.showError(err);
    } finally {
      this.exportBtn.disabled = false;
      this.exportBtn.textContent = originalLabel;
    }
  },

  // Fetches the page at the current offset from the materialised result.
  //
  // Reads the temp table, never the user's SQL. Re-running the query per page was the paging
  // bug: a subquery's ORDER BY is not guaranteed to survive being wrapped, and DuckDB scans in
  // parallel, so each execution could order rows differently — page 18 would show rows from
  // page 3, and the buttons looked dead because the content shuffled instead of moving. It was
  // also a full re-scan over HTTP for every page turn.
  async fetchPage() {
    const from = this.offset;
    const result = await this.conn.query(
      `SELECT * EXCLUDE (_row) FROM ${PAGE_TABLE}
       WHERE _row > ${from} AND _row <= ${from + PAGE_SIZE} ORDER BY _row`
    );
    this.renderResults(result);
  },

  async goToPage(delta) {
    if (!this.baseSql || this.paging) return;
    const nextOffset = this.offset + delta * PAGE_SIZE;
    if (nextOffset < 0 || nextOffset >= this.totalRows) return;

    // `offset` is mutated before an await, so two quick clicks would both advance it and then
    // race their fetches — the slower one wins the render and the table stops matching the
    // page number. One page turn at a time instead.
    this.paging = true;
    this.prevBtn.disabled = true;
    this.nextBtn.disabled = true;

    const previousOffset = this.offset;
    this.offset = nextOffset;
    this.clearError();
    try {
      await this.fetchPage();
      this.syncUrl();
    } catch (err) {
      // Put the offset back: the page on screen is still the old one, and leaving `offset`
      // ahead of it makes every later calculation describe a page nobody is looking at.
      this.offset = previousOffset;
      this.showError(err);
    } finally {
      this.paging = false;
      this.updatePaginationUI();
    }
  },

  async run() {
    this.clearError();
    this.runBtn.disabled = true;
    // Same shape as the export button below. A query runs two round trips — a wrapping COUNT,
    // then the first page — so on a cold cache there is a real pause with nothing else to see.
    const originalLabel = this.runBtn.textContent;
    this.runBtn.innerHTML = '<span class="spinner"></span>Running…';
    History.add(this.queryEl.value);
    const sql = this.queryEl.value.trim().replace(/;\s*$/, "");

    try {
      // Execute once, into a temp table, and page over that. Only the DOM ever holds a page,
      // so a large result (the whole 21k-row memberships table, say) still renders lazily —
      // but the scan, and any ORDER BY in it, happens a single time.
      //
      // Only works for SELECT-shaped queries; DESCRIBE/PRAGMA and friends cannot be wrapped
      // and fall through to the unpaginated path below.
      await this.conn.query(
        `CREATE OR REPLACE TEMP TABLE ${PAGE_TABLE} AS
         SELECT row_number() OVER () AS _row, * FROM (${sql}) AS _q`
      );
      const countResult = await this.conn.query(`SELECT COUNT(*) AS cnt FROM ${PAGE_TABLE}`);
      this.totalRows = Number(countResult.toArray()[0].cnt);
      this.baseSql = sql;
      // Clamp: the requested page only becomes meaningful once the row count exists.
      const lastOffset = Math.max(0, (Math.ceil(this.totalRows / PAGE_SIZE) - 1) * PAGE_SIZE);
      this.offset = Math.min((this.pendingPage - 1) * PAGE_SIZE, lastOffset);
      this.pendingPage = 1;
      await this.fetchPage();
      this.syncUrl();
    } catch {
      this.baseSql = null;
      this.paginationEl.hidden = true;
      try {
        const result = await this.conn.query(this.queryEl.value);
        this.renderResults(result);
      } catch (err) {
        this.showError(err);
        this.resultsWrap.innerHTML = "";
        this.metaEl.textContent = "";
        this.exportBtn.disabled = true;
      }
    } finally {
      this.runBtn.disabled = false;
      this.runBtn.textContent = originalLabel;
    }
  },
};
