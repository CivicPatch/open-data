import os
import glob
import yaml
import sys

# Import the function from process_jurisdiction.py
sys.path.append(os.path.dirname(__file__))
from process_jurisdiction import process_jurisdiction

ROOT_PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
DATA_SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../data_source'))
LOCAL_PATTERN = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../data/**/local/*.yml'))

def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def save_yaml(data, path):
    with open(path, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def get_first_person(jurisdiction_file):
    people = load_yaml(jurisdiction_file)
    if not people:
        return None
    return people[0]

def find_state_from_jurisdiction_file(jurisdiction_file):
    # Example: data/tx/houston/local/people.yml -> tx
    parts = jurisdiction_file.split(os.sep)
    try:
        idx = parts.index('data')
        return parts[idx + 1]
    except (ValueError, IndexError):
        return None

def main():
    # Find all jurisdiction files
    updated_jurisdiction_ocdids = set()
    jurisdiction_files = glob.glob(LOCAL_PATTERN, recursive=True)
    # Group jurisdiction files by state
    state_to_jurisdiction_files = {}
    for jurisdiction_file in jurisdiction_files:
        state = find_state_from_jurisdiction_file(jurisdiction_file)
        if not state:
            continue
        state_to_jurisdiction_files.setdefault(state, []).append(jurisdiction_file)

    for state, jurisdiction_files in state_to_jurisdiction_files.items():
        metadata_path = os.path.join(DATA_SOURCE_DIR, state, 'jurisdictions_metadata.yml')
        if os.path.exists(metadata_path):
            metadata = load_yaml(metadata_path)
        else:
            continue

        print(f"Processing {len(jurisdiction_files)} jurisdiction files for state {state}...")

        updated = False
        for jurisdiction_file in jurisdiction_files:
            jurisdiction_person = get_first_person(jurisdiction_file)
            jurisdiction_ocdid = jurisdiction_person.get("jurisdiction_ocdid")
            jurisdiction_updated_at = jurisdiction_person.get("updated_at") 
            
            meta_entry = metadata["jurisdictions_by_id"].get(jurisdiction_ocdid, {})

            if not jurisdiction_person:
                continue

            meta_updated_at = meta_entry.get('updated_at')
            if not meta_updated_at or meta_updated_at < jurisdiction_updated_at:
                try:
                    updated_jurisdiction_ocdids.add(jurisdiction_ocdid)
                    people = process_jurisdiction(jurisdiction_ocdid, jurisdiction_file)
                    if jurisdiction_ocdid not in metadata["jurisdictions_by_id"]:
                        metadata["jurisdictions_by_id"][jurisdiction_ocdid] = {}
                    meta_entry["updated_at"] = jurisdiction_updated_at
                    meta_entry["child_divisions"] = extract_child_divisions(people)
                    updated = True
                except Exception as e:
                    print(f"Error processing {jurisdiction_ocdid}: {e}")

        if updated:
            save_yaml(metadata, metadata_path)
            print(f"Updated {metadata_path}")

    # Save updated jurisdiction OCDIDs to a file for use in the GitHub Action workflow
    updated_ocdids_path = os.path.join(ROOT_PROJECT, 'updated_jurisdiction_ocdids.txt')
    print(f"Saving updated jurisdiction OCDIDs to {updated_ocdids_path}...")
    with open(updated_ocdids_path, 'w') as f:
        for ocdid in sorted(updated_jurisdiction_ocdids):
            f.write(f"{ocdid}\n")

def extract_child_divisions(people):
    child_divisions = set()
    for member in people:
        office = member.get("office", {})
        division = office.get("division_ocdid", "")
        child_divisions.add(division)
    return child_divisions

if __name__ == "__main__":
    main()