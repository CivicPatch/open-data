import os
import glob
import yaml
import re
import shutil

PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

def convert_to_division_ocdids(file_paths=None):
    """
    Update division_id to division_ocdid (just field change)
    """

    if file_paths is None:
        # Find all YAML files recursively (adjust pattern as needed)
        file_paths = glob.glob(os.path.join(PROJECT_PATH, "**/*.yml"), recursive=True)
        print(f"Found {len(file_paths)} YAML files to process")

    for file_path in file_paths:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, list):
            continue

        for item in data:
            office = item.get("office")
            if not office or not isinstance(office, dict):
                continue

            div_id = office.pop("division_id", None)
            if div_id is not None:
                office["division_ocdid"] = div_id

        # Write back to file
        new_file_path = file_path
        with open(new_file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)
    
if __name__ == "__main__":
    convert_to_division_ocdids()