// Pinned above 1.30.0: @duckdb/duckdb-wasm@1.29.2 was briefly compromised
// with crypto-stealing malware in Sep 2025 (CVE-2025-59037) before npm
// pulled it. Do not float this to "latest" without checking advisories.
import * as duckdb from "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.30.0/+esm";

// The dataset is NOT served beside this page. civicpatch.org's daily job writes it to R2, so
// this repo stays YAML a human can read and diff — a parquet corpus rewritten nightly would
// bloat its history permanently. The cost of that choice is CORS: the bucket must allow this
// origin (cp-infrastructure/resources/r2.tf) or every fetch below fails its preflight.
//
// Only localhost is special. Anywhere the page is actually deployed should show real data, and
// a checkout should not — so the environment is chosen from where the page is served rather
// than configured, which means no build step and nothing to keep in step.
//
// No allowlist of deployed hosts, because there is nothing to protect: this data is public to
// anyone with curl, and CORS decides which origins may read it. A host nobody granted gets a
// 403 whichever URL this picks.
const LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"];

const DATA_BASE = LOCAL_HOSTS.includes(location.hostname)
  ? "https://civicpatch-nonprod.civicpatch.org/parquet/"
  : "https://cdn.civicpatch.org/parquet/";

// DuckDB-Wasm's internal HTTP filesystem (used by read_parquet) does not
// resolve relative paths against the page URL the way fetch()/<img src>
// do — it needs an absolute http(s) URL, so every path handed to
// read_parquet() is resolved through this first.
function absUrl(relativePath) {
  // `DATA_BASE` is absolute here, so the second argument is inert — kept because the URL
  // constructor still needs a base and because a local dataset would want it.
  return new URL(relativePath, document.baseURI).href;
}

// DuckDB-Wasm init + registering Parquet views from the published manifest.
export const Dataset = {
  // Call this immediately at page load, in parallel with initDb() — it's a
  // plain HTTP fetch with no dependency on DuckDB being ready, so there's no
  // reason to wait for WASM init before starting it. Pass the returned
  // promise into registerViews() once the connection is ready.
  async fetchManifest() {
    // `no-cache` forces revalidation, not a bypass: the CDN in front of R2 caches objects with
    // its own TTL, and this dataset is rewritten daily. Without it a returning reader can query
    // yesterday's manifest against today's files. The ETag makes the revalidation cheap — an
    // unchanged manifest comes back 304 with no body.
    const resp = await fetch(DATA_BASE + "manifest.json", { cache: "no-cache" });
    if (!resp.ok) throw new Error(`Failed to load manifest.json (${resp.status})`);
    return resp.json();
  },

  async initDb() {
    const bundles = duckdb.getJsDelivrBundles();
    const bundle = await duckdb.selectBundle(bundles);

    const workerUrl = URL.createObjectURL(
      new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" })
    );

    const worker = new Worker(workerUrl);
    const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
    const db = new duckdb.AsyncDuckDB(logger, worker);
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    URL.revokeObjectURL(workerUrl);

    return db;
  },

  async registerViews(conn, manifestPromise) {
    const manifest = await manifestPromise;
    // Every parquet URL carries the manifest's own timestamp. DuckDB-Wasm fetches these through
    // its internal HTTP filesystem, which we cannot hand a `cache` option — so the version is
    // put in the URL instead. A run that changed nothing reuses the cached bytes; a new run
    // changes every URL at once, so the file list and the files can never disagree.
    const version = encodeURIComponent(manifest.generated_at ?? "");
    const versioned = (path) => `${absUrl(DATA_BASE + path)}?v=${version}`;

    const tableNames = [];
    // Row counts and column schema are both computed once at export time
    // (src/utils/parquet.py) and published in the manifest — reuse them
    // rather than re-deriving live in the browser.
    const rowCounts = new Map();
    const manifestTables = [];
    for (const entry of manifest.tables) {
      const safeName = `"${entry.name.replace(/"/g, '""')}"`;

      if (entry.file) {
        // Single unpartitioned file.
        await conn.query(
          `CREATE VIEW ${safeName} AS SELECT * FROM read_parquet('${versioned(entry.file)}')`
        );
      } else if (entry.files && Object.keys(entry.files).length > 0) {
        // Hive-partitioned table written as separate per-partition files.
        // hive_partitioning=true lets DuckDB infer the partition column
        // (e.g. state) from each file's path and prune remote fetches on
        // filtered queries, without needing directory listing over HTTP.
        const urls = Object.values(entry.files).map(versioned);
        const urlList = urls.map((u) => `'${u}'`).join(", ");
        await conn.query(
          `CREATE VIEW ${safeName} AS SELECT * FROM read_parquet([${urlList}], hive_partitioning=true)`
        );
      } else {
        // No partition files (e.g. a table with zero rows this run) — nothing to query.
        continue;
      }
      tableNames.push(entry.name);
      rowCounts.set(entry.name, entry.rows);
      manifestTables.push(entry);
    }
    return { tableNames, rowCounts, manifestTables };
  },
};
