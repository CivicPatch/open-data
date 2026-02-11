# For all jurisdictions_metadata.yml files under each state, 
# Remove the "jurisdiction" field and "jurisdiction_ocdid_slug"
import os
import glob
import yaml

SCRIPT_PATH = os.path.abspath(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def main():
    print("project root:", PROJECT_ROOT)
    for metadata_path in glob.glob(os.path.join(PROJECT_ROOT, "data_source/*/jurisdictions_metadata.yml")):
        print("found metadata file:", metadata_path)
        with open(metadata_path, "r") as f:
            metadata = yaml.safe_load(f)

        for jurisdiction_id, jurisdiction_data in metadata.get("jurisdictions_by_id", {}).items():
            if "jurisdiction" in jurisdiction_data:
                del jurisdiction_data["jurisdiction"]
            if "jurisdiction_ocdid_slug" in jurisdiction_data:
                del jurisdiction_data["jurisdiction_ocdid_slug"]

        with open(metadata_path, "w") as f:
            yaml.dump(metadata, f, sort_keys=False, allow_unicode=True)

        print(f"Updated {metadata_path}")

if __name__ == "__main__":
    main()