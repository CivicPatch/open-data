import yaml
import sys
from pathlib import Path
import glob
import re
from schemas import JurisdictionId

PROJECT_ROOT = Path(__file__).parent.parent

def extract_child_divisions(government_list, jurisdiction_id):
    child_divisions = []
    base_id = "/".join(jurisdiction_id.split("/")[:-1])
    for member in government_list:
        divisions = member.get("divisions", [])
        for division in divisions:
            # Check for 'district' and extract number/name
            district_match = re.search(r'district\s*:?[\s\-]*(\w+)', str(division), re.IGNORECASE)
            if district_match:
                district_num = district_match.group(1)
                child_divisions.append(f"{base_id}/council_district:{district_num}")
            # Check for 'ward' and extract number/name
            ward_match = re.search(r'ward\s*:?[\s\-]*(\w+)', str(division), re.IGNORECASE)
            if ward_match:
                ward_num = ward_match.group(1)
                child_divisions.append(f"{base_id}/ward:{ward_num}")
    return child_divisions

def create_update_progress_file(state: str):
    print("Create/updating progress file...")
    jurisdictions_file_path = PROJECT_ROOT / "data_source" / state / "jurisdictions.yml"
    progress_file_path = PROJECT_ROOT / "data_source" / state / "government_progress.yml"
    jurisdictions_data = yaml.safe_load(jurisdictions_file_path.read_text(encoding="utf-8"))
    jurisdictions = jurisdictions_data["jurisdictions"]
    files_found = 0
    warnings = []

    progress_data = { "jurisdictions_by_id": {}, "warnings": []}
    for jurisdiction in jurisdictions:
        jurisdiction_id = jurisdiction["id"]
        jurisdiction_object = {
            "jurisdiction_id": jurisdiction_id,
            "jurisdiction": {
                **jurisdiction
            },
            "child_divisions": []  # Add empty child_divisions list
        }
        progress_data["jurisdictions_by_id"][jurisdiction_id] = jurisdiction_object

    for place_file_path in list(glob.glob(f"data/{state}/*.yml")):
        files_found += 1
        with open(place_file_path, 'r') as f:
            place_data = yaml.safe_load(f)
        government_list = place_data.get("government", [])

        if not government_list:
            warnings.append(f"Empty file under {place_file_path}")
            continue

        place_data_updated_at = government_list[0].get("updated_at")
        place_jurisdiction_id = government_list[0].get("jurisdiction_id")

        if progress_data["jurisdictions_by_id"].get(place_jurisdiction_id) is None:
            warnings.append(f"Could not find matching jurisdiction id for {place_jurisdiction_id}")
            continue

        # Extract child divisions from government members
        child_divisions = extract_child_divisions(government_list, place_jurisdiction_id)

        jurisdiction_object = progress_data["jurisdictions_by_id"][place_jurisdiction_id]
        jurisdiction_object["updated_at"] = place_data_updated_at
        jurisdiction_object["child_divisions"] = child_divisions
        progress_data["jurisdictions_by_id"][place_jurisdiction_id] = jurisdiction_object
        
    progress_data["warnings"] = warnings
    num_jurisdictions = len(progress_data["jurisdictions_by_id"].values())
    num_jurisdictions_with_urls = sum(1 for j in jurisdictions if j.get("url"))

    progress_data["num_jurisdictions"] = num_jurisdictions
    progress_data["num_jurisdictions_with_urls"] = num_jurisdictions_with_urls
    progress_data["percentage_scrapeable"] = (num_jurisdictions_with_urls/num_jurisdictions)*100 if num_jurisdictions else 0
    progress_data["percentage_scraped"] = (files_found / num_jurisdictions) * 100 if num_jurisdictions else 0
    progress_data["percentage_scraped_from_scrapeable"] = (files_found / num_jurisdictions_with_urls) * 100 if num_jurisdictions_with_urls else 0
    with open(progress_file_path, 'w') as f:
        yaml.dump(progress_data, f, sort_keys=False)

    print(f"Number of jurisdictions in {state}: {num_jurisdictions}")
    print(f"Number of jurisdictions with urls: {num_jurisdictions_with_urls}")
    print(f"Number of jurisdictions scraped: {files_found}")
    print(f"Percentage scrapeable: {progress_data['percentage_scrapeable']:.2f}%")
    print(f"Percentage scraped (total): {progress_data['percentage_scraped']:.2f}%")
    print(f"Percentage scraped (from scrapeable): {progress_data['percentage_scraped_from_scrapeable']:.2f}%")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_update_progress_file.py <state>")
        sys.exit(1)
    state = sys.argv[1]
    create_update_progress_file(state)
