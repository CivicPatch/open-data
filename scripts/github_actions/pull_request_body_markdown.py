import sys
from scripts.utils import jurisdiction_ocdid_to_folder
import os
import yaml

def pull_request_body_markdown(jurisdiction_ocdid: str, request_id: str) -> str:
    """
    Generate a markdown-formatted pull request body for updating a jurisdiction's OCDID.

    Args:
        jurisdiction_ocdid (str): The OCDID of the jurisdiction being updated.
        request_id (str): The ID of the request being processed.

    Returns:
        str: The markdown-formatted pull request body.
    """

    jurisdiction_folder = jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    jurisdiction_data_source_folder = os.path.join("data_source", jurisdiction_folder)
    config_file = os.path.join(jurisdiction_data_source_folder, "config.yml")
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

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

"""

def markdown_list_br(items):
    return "<br>".join(f"- {item}" for item in items) if items else "N/A"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python pull_request_body_markdown.py <jurisdiction_ocdid> <request_id>")
        sys.exit(1)

    jurisdiction_ocdid = sys.argv[1]
    request_id = sys.argv[2]
    pr_body = pull_request_body_markdown(jurisdiction_ocdid, request_id)
    print(pr_body)