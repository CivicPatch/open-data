const QUERY_EXAMPLES = [
  {
    label: "The roster on a given date",
    description:
      "A membership is a row that is open over an interval, so an as-of question keeps the rows whose interval covers the date. Mind what the interval means: first_seen_at is when we first observed the seat, not when the term began — start_date carries the claimed term, as free text. So a date before we collected a place returns nothing for it. The date is written twice; change both.",
    sql: "SELECT p.name, r.label AS seat,\n       strftime(m.first_seen_at AT TIME ZONE 'UTC', '%Y-%m-%d') AS first_seen,\n       strftime(m.closed_at     AT TIME ZONE 'UTC', '%Y-%m-%d') AS closed\nFROM memberships m\nJOIN people p ON p.id = m.person_id\nJOIN posts po ON po.id = m.post_id\nJOIN roles r ON r.id = po.role_id\nJOIN jurisdictions j ON j.jurisdiction_ocdid = m.jurisdiction_ocdid\nWHERE j.state = 'wa' AND j.name = 'Tacoma city'\n  AND m.first_seen_at <= DATE '2026-01-15'\n  AND (m.closed_at IS NULL OR m.closed_at > DATE '2026-01-15')\nORDER BY r.priority NULLS LAST, p.name;",
  },
  {
    label: "Who holds a seat in one place",
    description:
      "The core join: a membership links a person to a post, the post carries the role. Note the name is \"Seattle city\" — OCD names keep their type suffix, so match with ILIKE rather than =.",
    sql: "SELECT p.name, r.label AS seat, j.name AS jurisdiction\nFROM memberships m\nJOIN people p ON p.id = m.person_id\nJOIN posts po ON po.id = m.post_id\nJOIN roles r ON r.id = po.role_id\nJOIN jurisdictions j ON j.jurisdiction_ocdid = m.jurisdiction_ocdid\nWHERE m.is_open AND j.state = 'wa' AND j.name ILIKE 'Seattle%'\nORDER BY r.priority NULLS LAST, p.name;",
  },
  {
    label: "Former officeholders",
    description:
      "What the published YAML cannot answer: it renders the live roster only, so a seat that ended leaves no trace there. Here it is a row with is_open false.",
    sql: "SELECT p.name, r.label AS seat, j.name AS jurisdiction,\n       m.first_seen_at, m.closed_at\nFROM memberships m\nJOIN people p ON p.id = m.person_id\nJOIN posts po ON po.id = m.post_id\nJOIN roles r ON r.id = po.role_id\nJOIN jurisdictions j ON j.jurisdiction_ocdid = m.jurisdiction_ocdid\nWHERE NOT m.is_open\nORDER BY m.closed_at DESC;",
  },
  {
    label: "Seats nobody holds",
    description:
      "Anti-join: a post with no open membership. Either a vacancy, or a seat we have not matched anyone to yet.",
    sql: "SELECT j.name AS jurisdiction, r.label AS seat, po.division_ocdid\nFROM posts po\nJOIN roles r ON r.id = po.role_id\nJOIN jurisdictions j ON j.jurisdiction_ocdid = po.jurisdiction_ocdid\nLEFT JOIN memberships m ON m.post_id = po.id AND m.is_open\nWHERE m.id IS NULL\nORDER BY j.state, j.name;",
  },
  {
    label: "Coverage by state",
    description:
      "How much of each state we hold. Rows are written ordered by state, so a filter on it skips whole row groups rather than reading the file.",
    sql: "SELECT state,\n       COUNT(DISTINCT jurisdiction_ocdid) AS jurisdictions,\n       COUNT(*) FILTER (WHERE is_open)    AS open_seats\nFROM memberships\nGROUP BY state\nORDER BY open_seats DESC;",
  },
  {
    label: "The same name in different places",
    description:
      "Four different Mike Hills, in four different towns — not one person with four seats. A person row belongs to one jurisdiction, so identity is person_id and never the name. Nobody in this dataset holds two open seats at once.",
    sql: "SELECT p.name,\n       COUNT(*) AS people,\n       LIST(j.name ORDER BY j.name) AS jurisdictions\nFROM people p\nJOIN jurisdictions j ON j.jurisdiction_ocdid = p.jurisdiction_ocdid\nGROUP BY p.name\nHAVING COUNT(*) > 1\nORDER BY people DESC, p.name;",
  },
  {
    label: "Search a name across every state",
    description:
      "Looks in other_names too — the list column that survives here as a real list rather than a joined string.",
    sql: "SELECT name, other_names, emails, jurisdiction_ocdid\nFROM people\nWHERE name ILIKE '%rinck%'\n   OR list_contains(other_names, 'Alexis Mercedes Rinck');",
  },
  {
    label: "The role taxonomy, by how much it is used",
    description:
      "Roles are global — they name no jurisdiction. `priority` is what orders a person's seats against each other.",
    sql: "SELECT r.id, r.label, r.status, r.is_unique, r.priority,\n       COUNT(po.id) AS posts\nFROM roles r\nLEFT JOIN posts po ON po.role_id = r.id\nGROUP BY ALL\nORDER BY posts DESC;",
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
