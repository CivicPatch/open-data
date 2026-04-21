"""
Update the URL for a jurisdiction in jurisdictions.yml based on the resolved URL
recorded in the pipeline run context JSON.

Usage:
    python update_jurisdiction_url.py <jurisdiction_ocdid> <pipeline_run_context_json_path>
"""

import json
import sys
from pathlib import Path

from ruamel.yaml import YAML

from shared.schemas import PipelineRunConfig
from scripts.utils import parse_jurisdiction_ocdid


def update_jurisdiction_url(jurisdiction_ocdid: str, context_json_path: str) -> None:
    context_path = Path(context_json_path)
    if not context_path.exists():
        print(f"Context file not found: {context_json_path}")
        return

    with open(context_path) as f:
        context = json.load(f)

    config_data = context.get("data", {}).get("config")
    if not config_data:
        print("No config found in pipeline context")
        return

    config = PipelineRunConfig.model_validate(config_data)
    resolved_url = config.url

    parsed = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    jurisdictions_path = Path(f"data_source/{parsed.state}/jurisdictions.yml")
    if not jurisdictions_path.exists():
        print(f"Jurisdictions file not found: {jurisdictions_path}")
        return

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    with open(jurisdictions_path) as f:
        data = yaml.load(f)

    for entry in data.get("jurisdictions", []):
        if entry.get("id") != jurisdiction_ocdid:
            continue
        if entry.get("url") == resolved_url:
            print(f"URL unchanged for {jurisdiction_ocdid}: {resolved_url}")
        else:
            print(f"Updating URL for {jurisdiction_ocdid}: {entry['url']} -> {resolved_url}")
            entry["url"] = resolved_url
            with open(jurisdictions_path, "w") as f:
                yaml.dump(data, f)
            print(f"Updated {jurisdictions_path}")
        return

    print(f"Jurisdiction not found in {jurisdictions_path}: {jurisdiction_ocdid}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python update_jurisdiction_url.py <jurisdiction_ocdid> <pipeline_run_context_json_path>")
        sys.exit(1)
    update_jurisdiction_url(sys.argv[1], sys.argv[2])
