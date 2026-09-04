import { Theme } from "./theme.js";
import { Dataset } from "./dataset.js";
import { SchemaPanel } from "./schema-panel.js";
import { QueryRunner } from "./query-runner.js";
import { Examples } from "./examples.js";
import { History } from "./history.js";

const statusEl = document.getElementById("status");
const tablesHintEl = document.getElementById("tables-hint");

Theme.init();

function wireModal(toggleId, modalId, closeId) {
  const modal = document.getElementById(modalId);
  document.getElementById(toggleId).addEventListener("click", () => modal.showModal());
  document.getElementById(closeId).addEventListener("click", () => modal.close());
  return modal;
}
const examplesModal = wireModal("examples-toggle", "examples-modal", "examples-close");
wireModal("definitions-toggle", "definitions-modal", "definitions-close");
const historyModal = wireModal("history-toggle", "history-modal", "history-close");

document.getElementById("history-toggle").addEventListener("click", () => {
  History.render((sql) => {
    QueryRunner.setQuery(sql);
    QueryRunner.run();
    historyModal.close();
  });
});

(async () => {
  try {
    // Kicked off before WASM init — manifest.json has no dependency on
    // DuckDB being ready, so there's no reason to wait for it. Both
    // requests run concurrently instead of back-to-back.
    const manifestPromise = Dataset.fetchManifest();

    const db = await Dataset.initDb();
    const conn = await db.connect();
    QueryRunner.init(conn);

    statusEl.innerHTML = '<span class="spinner"></span>Loading dataset manifest…';
    const { tableNames, rowCounts, manifestTables } = await Dataset.registerViews(conn, manifestPromise);

    const onSelectTable = (table) => {
      QueryRunner.setQuery(`SELECT * FROM ${table};`);
      QueryRunner.run();
    };
    SchemaPanel.renderNames(tableNames, rowCounts, onSelectTable);
    SchemaPanel.renderDefinitions(manifestTables);

    Examples.render((sql) => {
      QueryRunner.setQuery(sql);
      QueryRunner.run();
      examplesModal.close();
    });

    statusEl.textContent = "Ready.";
    tablesHintEl.textContent = tableNames.length
      ? `${tableNames.length} table${tableNames.length === 1 ? "" : "s"} available — click a table name above to preview it`
      : "No tables found in manifest.";

    // A URL carrying ?sql= wins: the reader followed a link to a specific result, and
    // overwriting it with the default query would discard what they came for.
    const requested = QueryRunner.fromUrl();
    if (requested) {
      QueryRunner.setQuery(requested.sql);
      QueryRunner.pendingPage = requested.page;
    } else {
      QueryRunner.setQuery(
        tableNames.includes("memberships")
          ? "SELECT * FROM memberships WHERE is_open;"
          : tableNames.length
            ? `SELECT * FROM ${tableNames[0]};`
            : "-- No tables available"
      );
    }

    QueryRunner.runBtn.disabled = false;
    if (tableNames.length) QueryRunner.run();
  } catch (err) {
    statusEl.textContent = "";
    QueryRunner.showError(err);
  }
})();
