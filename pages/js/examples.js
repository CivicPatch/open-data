const QUERY_EXAMPLES = [
  {
    label: "Who holds a seat in one place",
    description:
      "The basic join. A membership links a person to a post; the post belongs to a jurisdiction.",
    sql: "SELECT p.name, m.label AS seat, j.name AS jurisdiction\nFROM memberships m\nJOIN people p ON p.id = m.person_id\nJOIN jurisdictions j ON j.jurisdiction_ocdid = m.jurisdiction_ocdid\nWHERE m.is_open AND j.name = 'Seattle'\nORDER BY p.name;",
  },
  {
    label: "Former officeholders",
    description:
      "What the git files cannot answer. Open-data renders the live roster only, so a seat that ended is invisible there — here it is a row with is_open false.",
    sql: "SELECT p.name, m.label AS seat, m.first_seen_at, m.closed_at\nFROM memberships m\nJOIN people p ON p.id = m.person_id\nWHERE NOT m.is_open\nORDER BY m.closed_at DESC\nLIMIT 50;",
  },
  {
    label: "Seats nobody holds",
    description:
      "Anti-join: posts with no open membership. A vacancy, or a seat we have not matched anyone to yet.",
    sql: "SELECT j.name AS jurisdiction, po.role_id, po.division_ocdid\nFROM posts po\nJOIN jurisdictions j ON j.jurisdiction_ocdid = po.jurisdiction_ocdid\nLEFT JOIN memberships m ON m.post_id = po.id AND m.is_open\nWHERE m.id IS NULL\nORDER BY j.name\nLIMIT 50;",
  },
  {
    label: "Coverage by state",
    description:
      "How much of each state we hold. `state` comes from the partition path, not from a column.",
    sql: "SELECT state,\n       COUNT(DISTINCT jurisdiction_ocdid) AS jurisdictions,\n       COUNT(*) FILTER (WHERE is_open) AS open_seats\nFROM memberships\nGROUP BY state\nORDER BY open_seats DESC;",
  },
  {
    label: "People holding more than one seat",
    description:
      "A mayor who also sits on a board. One person, several memberships — which is why the dates live on the membership and not on the person.",
    sql: "SELECT p.name, COUNT(*) AS seats, LIST(m.label) AS held\nFROM memberships m\nJOIN people p ON p.id = m.person_id\nWHERE m.is_open\nGROUP BY p.name\nHAVING COUNT(*) > 1\nORDER BY seats DESC\nLIMIT 50;",
  },
  {
    label: "Search a name across every state",
    description:
      "Case-insensitive, and it looks in other_names too — the list column that survives here as a real list rather than a joined string.",
    sql: "SELECT name, other_names, jurisdiction_ocdid\nFROM people\nWHERE name ILIKE '%rinck%'\n   OR list_contains(other_names, 'Alexis Mercedes Rinck')\nLIMIT 20;",
  },
  {
    label: "The role taxonomy",
    description:
      "Roles are global — they name no jurisdiction — so this table is one file rather than fifty. `priority` is what orders a person's own seats.",
    sql: "SELECT id, label, status, is_unique, priority\nFROM roles\nORDER BY priority NULLS LAST, label;",
  },
];

// Static, hand-written example queries shown in a modal. No DB access needed — unlike
// SchemaPanel, this list does not depend on what tables happen to exist at runtime.
export const Examples = {
  el: document.getElementById("examples-list"),

  render(onSelectExample) {
    this.el.innerHTML = QUERY_EXAMPLES.map(
      (ex, i) => `
        <div class="example-item">
          <button type="button" class="example-name" data-index="${i}">${ex.label}</button>
          <div class="example-desc">${ex.description}</div>
          <pre class="example-sql">${ex.sql}</pre>
        </div>
      `
    ).join("");

    this.el.querySelectorAll(".example-name").forEach((btn) => {
      btn.addEventListener("click", () => {
        onSelectExample(QUERY_EXAMPLES[Number(btn.dataset.index)].sql);
      });
    });
  },
};
