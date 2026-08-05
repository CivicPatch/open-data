import json
import os
import sys

# Import the function from process_jurisdiction_data.py
sys.path.append(os.path.dirname(__file__))
from scripts.github_actions.local.post_merge.process_jurisdiction_data import process_jurisdiction
from shared.utils.yaml_utils import yaml_load, yaml_dump

ROOT_PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))

# stdout carries the result — a JSON array of the jurisdiction OCDIDs processed — so the
# caller can capture it. Everything else is progress reporting and belongs on stderr.
def log(message):
    print(message, file=sys.stderr)

# People files under data/ go through the shared manager so post-merge cdn_image rewrites
# keep them in the canonical style (no re-wrapping, explicit `null`).
def load_people(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return yaml_load(f.read())

def save_people(people, path):
    with open(path, 'w') as f:
        f.write(yaml_dump(people))

def read_changed_files():
    return [line.strip() for line in sys.stdin if line.strip()]

def emit_updated_ocdids(ocdids):
    log(f"Processed {len(ocdids)} updated jurisdictions.")
    print(json.dumps(sorted(ocdids)))

def main():
    changed_files = read_changed_files()
    updated_jurisdiction_ocdids = set()

    log(f"Processing {len(changed_files)} changed jurisdiction files...")

    for relative_path in changed_files:
        jurisdiction_file = os.path.join(ROOT_PROJECT, relative_path)
        people = load_people(jurisdiction_file)
        if not people:
            continue

        jurisdiction_ocdid = people[0].get("jurisdiction_ocdid")
        if not jurisdiction_ocdid:
            continue

        updated_jurisdiction_ocdids.add(jurisdiction_ocdid)
        try:
            people, images_updated = process_jurisdiction(jurisdiction_ocdid, jurisdiction_file, people)
            if images_updated:
                save_people(people, jurisdiction_file)
        except Exception as e:
            log(f"Error processing {jurisdiction_ocdid}: {e}")
            raise

    emit_updated_ocdids(updated_jurisdiction_ocdids)

if __name__ == "__main__":
    main()
