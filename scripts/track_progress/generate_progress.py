"""
generate_readme.py  —  generate README.md from per-state output JSON files

Automatically discovers all state output files via glob.

Usage:
    python generate_readme.py

Example:
    python generate_readme.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR     = PROJECT_ROOT / "scripts/track_progress/data"
OUTPUT_FILE  = PROJECT_ROOT / "README.md"


def discover_states() -> list[str]:
    """Glob for all *_output.json files and return sorted list of state codes."""
    files = sorted(DATA_DIR.glob("*_output.json"))
    return [f.name.replace("_output.json", "").upper() for f in files]


def load_state(state: str) -> dict:
    path = DATA_DIR / f"{state.lower()}_output.json"
    with open(path) as f:
        return json.load(f)


def fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{value:.0%}"


def generate_readme():
    states = discover_states()
    if not states:
        print(f"ERROR: no *_output.json files found in {DATA_DIR}")
        sys.exit(1)

    state_data = {}
    for state in states:
        try:
            state_data[state] = load_state(state)
        except FileNotFoundError:
            print(f"  WARN: could not load {state}, skipping")

    if not state_data:
        print("ERROR: no state data loaded")
        sys.exit(1)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Coverage table ────────────────────────────────────────────────────────
    header  = "| State | CP Officials | CP Coverage | CP Scrapeable | CP Known | Ext Officials | Ext Coverage | Ext Known | Name Match |"
    divider = "|-------|-------------|-------------|---------------|----------|---------------|--------------|-----------|------------|"
    rows = []
    for state, data in sorted(state_data.items()):
        s   = data["summary"]
        cp  = s["civicpatch"]
        ext = s["external"]
        mq  = s["match_quality"]
        rows.append(
            f"| {state} "
            f"| {cp['officials']:,} "
            f"| {cp['localities']['coverage']:,} "
            f"| {cp['localities']['scrapeable']:,} "
            f"| {cp['localities']['known']:,} "
            f"| {ext['officials']:,} "
            f"| {ext.get('coverage', '—'):,} "
            f"| {ext['localities']:,} "
            f"| {fmt_pct(mq['name_match_pct'])} |"
        )
    coverage_table = "\n".join([header, divider] + rows)

    # ── Locality gaps ─────────────────────────────────────────────────────────
    gaps_sections = []
    for state, data in sorted(state_data.items()):
        gaps        = data["summary"]["locality_gaps"]
        not_scraped = gaps.get("not_yet_scraped", [])
        not_known   = gaps.get("in_external_not_known", [])

        section  = f"### {state}\n\n"
        section += "<details>\n"
        cp_not_ext_count = len(gaps.get("in_civicpatch_not_external", []))
        section += f"<summary>{len(not_scraped)} not yet scraped &nbsp;·&nbsp; {len(not_known)} in external, not in CP &nbsp;·&nbsp; {cp_not_ext_count} in CP, not in external</summary>\n\n"

        section += "#### Not yet scraped\n\n"
        section += ("\n".join(f"- {j}" for j in not_scraped) if not_scraped else "None")
        section += "\n\n"

        cp_not_ext = gaps.get("in_civicpatch_not_external", [])
        max_rows   = max(len(not_known), len(cp_not_ext), 1)

        section += "#### Locality Gaps\n\n"
        section += "| In External, Not in Known | In CivicPatch, Not in External |\n"
        section += "|---------------------------|--------------------------------|\n"
        for i in range(max_rows):
            ext_val = not_known[i]  if i < len(not_known)  else ""
            cp_val  = cp_not_ext[i] if i < len(cp_not_ext) else ""
            section += f"| {ext_val} | {cp_val} |\n"
        section += "\n</details>\n"

        gaps_sections.append(section)

    gaps_content = "\n".join(gaps_sections)

    # ── Assemble README ───────────────────────────────────────────────────────
    readme = f"""# CivicPatch Data Quality

Generated: {generated_at}

## Coverage Summary

{coverage_table}

**Columns:** CP Officials = officials scraped · CP Coverage = localities with CP data · CP Scrapeable = localities with a URL · CP Known = all tracked localities · Ext Officials = external officials · Ext Coverage = external localities with officials data · Ext Known = all localities external source knows · Name Match = % of external names found in CP (localities with data in both)

## Locality Gaps

{gaps_content}
"""

    with open(OUTPUT_FILE, "w") as f:
        f.write(readme)

    # ── Dashboard JSON ────────────────────────────────────────────────────────
    dashboard = {
        "generated_at": generated_at,
        "states": {
            state: data["summary"]
            for state, data in sorted(state_data.items())
        },
    }
    dashboard_file = PROJECT_ROOT / "scripts/track_progress/data/dashboard.json"
    with open(dashboard_file, "w") as f:
        json.dump(dashboard, f, indent=2)

    print(f"✓ README.md written to {OUTPUT_FILE}")
    print(f"✓ dashboard.json written to {dashboard_file}")
    for state, data in sorted(state_data.items()):
        s  = data["summary"]
        cp = s["civicpatch"]["localities"]
        print(f"  {state}: {cp['coverage']} coverage / {cp['known']} known / {fmt_pct(s['match_quality']['name_match_pct'])} name match")


if __name__ == "__main__":
    generate_readme()