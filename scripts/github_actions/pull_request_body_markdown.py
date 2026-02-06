import sys
from scripts.utils import jurisdiction_ocdid_to_folder
import os
import yaml
import json
import requests

def pull_request_body_markdown(jurisdiction_ocdid: str, request_id: str, log_url: str) -> str:
    """
    Generate a markdown-formatted pull request body for updating a jurisdiction's OCDID.

    Args:
        jurisdiction_ocdid (str): The OCDID of the jurisdiction being updated.
        request_id (str): The ID of the request being processed.
        workflow_context_url (str): The debug URL of the workflow context.

    Returns:
        str: The markdown-formatted pull request body.
    """

    jurisdiction_folder = jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    jurisdiction_data_source_folder = os.path.join("data_source", jurisdiction_folder)
    workflow_context_path = os.path.join(jurisdiction_data_source_folder, "workflow_context.json")
    with open(workflow_context_path, "r") as f:
        workflow_context = json.load(f)

    config = workflow_context.get("data", {}).get("format_output_step", {}).get("config", {})

    # Extract relevant information from the config
    jurisdiction_url = config.get("url", "N/A")
    jurisdiction_name = config.get("name", "Unknown Jurisdiction")
    jurisdiction_source_urls = config.get("source_urls", [])
    jurisdiction_identities = config.get("identities", [])

    source_urls_str = markdown_list_br(jurisdiction_source_urls)
    identities_str = markdown_list_br(jurisdiction_identities)

    return f"""# Data intake for {jurisdiction_ocdid}

## Jurisdiction Configs
Note: some configs, like source_urls and identities, are generated after the scrape.

| Field              | Value                                   |
|--------------------|-----------------------------------------|
| **Jurisdiction OCDID** | {jurisdiction_ocdid}                |
| **URL**                | {jurisdiction_url}                  |
| **Name**               | {jurisdiction_name}                 |
| **Source URLs**        | {source_urls_str}                   |
| **Identities**         | {identities_str}                    |

## Request Information
- **Request ID**: {request_id}
- **Log URL**: [Link]({log_url})

"""

def markdown_list_br(items):
    return "<br>".join(f"- {item}" for item in items) if items else "N/A"

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python pull_request_body_markdown.py <jurisdiction_ocdid> <request_id> <log_url>")
        sys.exit(1)

    jurisdiction_ocdid = sys.argv[1]
    request_id = sys.argv[2]
    log_url = sys.argv[3]
    pr_body = pull_request_body_markdown(jurisdiction_ocdid, request_id, log_url)
    print(pr_body)