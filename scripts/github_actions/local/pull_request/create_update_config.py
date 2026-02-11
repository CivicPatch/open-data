import os
import yaml
import argparse
import re

def create_update_config_file(data_file_path):
    print("Creating/updating config file based off of data file:", data_file_path)
    # Regex: data/x/y/z.yml -> data_source/x/y/z/config.yml
    config_path = re.sub(
        r'^data/([^/]+)/([^/]+)/([^/]+)\.yml$',
        r'data_source/\1/\2/\3/config.yml',
        data_file_path
    )
    print("Config file path:", config_path)

    # Load people data from YAML
    if not os.path.exists(data_file_path):
        print(f"Data file {data_file_path} not found.")
        return

    with open(data_file_path, "r") as f:
        people = yaml.safe_load(f)

    # Load existing config if it exists, otherwise start with empty config
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}

    # Gather all source URLs and identities
    source_urls = set()
    # Identities ex:
    # { "John Doe": ["J. Doe", "Jonathan Doe"] }
    identities = config.get("identities", {})
    canonical_names = set(identities.keys()) if identities else set()
    aliases = identities.values().flatten() if identities else []
    offices = []

    for person in people:
        # Collect source URLs
        sources = person.get("source_urls", [])
        source_urls.update(sources)

        # Collect identities
        other_names = person.get("other_names", [])
        person_name = person.get("name")
        if person_name not in canonical_names and person_name not in aliases:
            if other_names:
                identities[person_name] = other_names

        offices = [*offices, { "name": person.get("office").get("name"), "division_ocdid": person.get("office").get("division_ocdid") }] if person.get("office") else offices

    config["source_urls"] = sorted(source_urls)
    config["identities"] = identities
    config["offices"] = offices

    # Write back to config file
    with open(config_path, "w") as f:
        yaml.dump(config, f, sort_keys=False, allow_unicode=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a jurisdiction's files after a merge.")
    parser.add_argument("jurisdiction_ocdid", help="The OCDID of the jurisdiction to process.")
    args = parser.parse_args()
    create_update_config_file(args.jurisdiction_ocdid)