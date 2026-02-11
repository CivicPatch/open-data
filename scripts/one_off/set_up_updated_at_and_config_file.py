import os
import glob
import yaml

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data'))
DATA_SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data_source'))

def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def save_yaml(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def main():
    # Find all data/*/local/*.yml files
    yml_files = glob.glob(os.path.join(DATA_DIR, '*', 'local', '*.yml'))
    print(f"Found {len(yml_files)} jurisdiction files to process.")
    metadata_files = glob.glob(os.path.join(DATA_SOURCE_DIR, '*', 'jurisdictions_metadata.yml'))
    for metadata_file in metadata_files:
        print(f"Found metadata file: {metadata_file}")
        metadata = load_yaml(metadata_file)
        parts = metadata_file.split(os.sep)
        state = parts[-2]  # data_source/state/jurisdictions_metadata.yml

        # For every data file under the state, grab their updated_at from the first person
        yml_files_for_state = glob.glob(os.path.join(DATA_DIR, state, 'local', '*.yml'))

        for yml_file in yml_files_for_state:
            # print(f"Processing {yml_file}...")
            # Load people
            people = load_yaml(yml_file)
            if not people or not isinstance(people, list):
                continue

            jurisdiction_ocdid = people[0].get("jurisdiction_ocdid")
            print("jurisdiction_ocdid:", jurisdiction_ocdid)
            updated_at = people[0].get("updated_at")
            # --- Update jurisdictions_metadata.yml ---
            metadata["jurisdictions_by_id"][jurisdiction_ocdid]["updated_at"] = updated_at
            # config_file is just yml_file but with data_source instead of data and config.yml instead of xxxx.yml
            # /open-data/data/tx/houston/local/place_blah.yml -> /open-data/data_source/tx/houston/local/place_blah/config.yml
            config_path = yml_file.replace(DATA_DIR, DATA_SOURCE_DIR).replace('.yml', '/config.yml')

            # --- Generate config.yml ---
            source_urls = set()
            identities = {}
            offices = []
            for person in people:
                # source_urls
                source_urls = person.get("source_urls", [])
                unique_source_urls = set(source_urls)
                source_urls = unique_source_urls.union(source_urls)
                # identities
                canonical_name = person.get("name")
                other_names = person.get("other_names", [])
                if canonical_name and other_names:
                    identities[canonical_name] = other_names
                # offices
                office = person.get("office")
                if office:
                    offices.append({
                        "name": office.get("name", ""),
                        "division_ocdid": office.get("division_ocdid", "")
                    })
            config = {
                "source_urls": sorted(source_urls),
                "identities": identities,
                "offices": offices
            }
            save_yaml(config, config_path)
            #print(f"Generated {config_path}")

    save_yaml(metadata, metadata_file)

        

if __name__ == "__main__":
    main()