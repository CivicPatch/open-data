import os
import glob
import yaml
import re
import shutil

PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

def convert_to_division_ocdids(file_paths=None, delete_original=False):
    """
    Update division OCDIDs in YAML files (list of people) to include full hierarchy.
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
            jurisdiction_ocdid = item.get("jurisdiction_ocdid")
            office = item.get("office")
            if not jurisdiction_ocdid or not office or not isinstance(office, dict):
                continue

            # Extract the base division from jurisdiction_ocdid
            base_division = jurisdiction_ocdid.replace("ocd-jurisdiction", "ocd-division")
            base_division = re.sub(r"/government$", "", base_division)

            div_id = office.get("division_id")
            if div_id is None or div_id == "":
                office["division_id"] = base_division
            elif isinstance(div_id, str):
                ward_match = re.match(r"(?i)ward\s*:?[\s-]*(.+)", div_id)
                district_match = re.match(r"(?i)(council[_\s]?district|district)\s*:?[\s-]*(.+)", div_id)

                if ward_match:
                    office["division_id"] = f"{base_division}/ward:{ward_match.group(1).strip().replace(' ', '_').lower()}"
                elif district_match:
                    office["division_id"] = f"{base_division}/council_district:{district_match.group(2).strip().replace(' ', '_').lower()}"
                elif div_id.startswith("ocd-division/"):
                    continue
                else:
                    office["division_id"] = f"{base_division}"

        # Write back to file
        new_file_path = file_path
        with open(new_file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)

if __name__ == "__main__":
    convert_to_division_ocdids(delete_original=False)