"""Shared YAML read/write for `data_source/**/jurisdictions.yml`.

Extracted so the state and county generators no longer import private helpers out of
`local.py`. All three writers round-trip through the same ruamel configuration, which is
what preserves human comments and manual edits across regeneration.
"""

from pathlib import Path
from typing import Tuple

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

ryaml = YAML()
ryaml.preserve_quotes = True
ryaml.default_flow_style = False
ryaml.width = 4096


def _represent_none(representer, _):
    return representer.represent_scalar("tag:yaml.org,2002:null", "null")


ryaml.representer.add_representer(type(None), _represent_none)


def load_existing_jurisdictions(path: Path):
    """Load an existing jurisdictions.yml with ruamel.yaml (preserving comments).

    Returns (doc, existing_by_id) where:
      - doc is the full CommentedMap (top-level document), or {} if file absent
      - existing_by_id is a dict keyed by jurisdiction id pointing to CommentedMap entries
    """
    if not path.exists():
        return CommentedMap(), {}
    with open(path) as f:
        doc = ryaml.load(f)
    if not doc or "jurisdictions" not in doc:
        return doc or {}, {}
    return doc, {j["id"]: j for j in doc["jurisdictions"]}


def apply_scraped_fields(existing_entry, scraped) -> None:
    """Merge scraper output into an existing jurisdictions.yml entry.

    The single definition of the write-back contract, shared by the state, county and
    municipality writers:

      url                 write-once — a human may have corrected it
      wiki_url            refreshed every run
      issues              replaced; removed when the scrape reports none
      generated_comments  replaced; removed when the scrape reports none
      comments            never touched

    Previously each writer carried its own copy of these rules, which is how the county
    generator ended up documenting a `url` field it never populated.
    """
    if scraped.url and not existing_entry.get("url"):
        existing_entry["url"] = scraped.url
    if scraped.wiki_url:
        existing_entry["wiki_url"] = scraped.wiki_url

    for field in ("issues", "generated_comments"):
        value = getattr(scraped, field, None)
        if value:
            existing_entry[field] = value
        elif field in existing_entry:
            del existing_entry[field]


def get_names(name: str) -> Tuple[str, str]:
    """Split a Census NAME into (ocdid_slug, friendly_name).

    Example: "Gervais city, Oregon" -> ("gervais", "Gervais city")
    """
    parts = name.split(",")
    friendly_name = parts[0].strip()
    # Drop the trailing type word (city/town/County/...) to get the slug
    place_name_parts = friendly_name.split(" ")
    place_name = " ".join(place_name_parts[:-1]).lower()
    jurisdiction_name = place_name.replace(" ", "_")
    return jurisdiction_name, friendly_name
