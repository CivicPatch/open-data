import os
import glob
import yaml

PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

def move_dates_to_person(file_paths=None):
    """
    Move office.start_date and office.end_date to root-level person.start_date and person.end_date
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

            office_start_date = office.pop("start_date", None)
            office_end_date = office.pop("end_date", None)

            item["start_date"] = office_start_date
            item["end_date"] = office_end_date

        # Write back to file
        new_file_path = file_path
        with open(new_file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)
    
if __name__ == "__main__":
    move_dates_to_person()