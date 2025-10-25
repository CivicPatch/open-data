import yaml
import sys
from pathlib import Path
import glob

PROJECT_ROOT = Path(__file__).parent.parent

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
            }
        }
        progress_data["jurisdictions_by_id"][jurisdiction_id] = jurisdiction_object

    for place_file_path in list(glob.glob(f"data/{state}/*.yml")):
        files_found += 1
        place_progress = {}
        with open(place_file_path, 'r') as f:
            place_data = yaml.safe_load(f)
        place_data = place_data["government"]

        if not place_data:
            warnings.append(f"Empty file under {place_file_path}")
            continue

        # They *should* all be the same...
        place_data_updated_at = place_data[0]["updated_at"]
        place_jurisdiction_id = place_data[0]["jurisdiction_id"]

        if progress_data["jurisdictions_by_id"].get(place_jurisdiction_id) is None:
            warnings.append(f"Could not find matching jurisdiction id for {place_jurisdiction_id}")
        jurisdiction_object = progress_data["jurisdictions_by_id"][place_jurisdiction_id]
        progress_data["jurisdictions_by_id"][place_jurisdiction_id] = {
            **jurisdiction_object,
            "updated_at": place_data_updated_at
        }
        
    progress_data["warnings"] = warnings
    num_jurisdictions = len(progress_data["jurisdictions_by_id"].values())
    num_jurisdictions_with_urls = sum(1 for j in jurisdictions if j["url"])

    progress_data["num_jurisdictions"] = num_jurisdictions
    progress_data["num_jurisdictions_with_urls"] = num_jurisdictions_with_urls
    progress_data["percentage_scrapeable"] = (num_jurisdictions_with_urls/num_jurisdictions)*100
    progress_data["percentage_scraped"] = (files_found / num_jurisdictions) * 100
    progress_data["percentage_scraped_from_scrapeable"] = (files_found / num_jurisdictions_with_urls) * 100
    with open(progress_file_path, 'w') as f:
        yaml.dump(progress_data, f, sort_keys=False)

    print(f"Number of jurisdictions in {state}: {num_jurisdictions}")
    print(f"Number of jurisdictions with urls: {num_jurisdictions_with_urls}")
    print(f"Number of jurisdictions scraped: {files_found}")
    print(f"Percentage scrapeable: {progress_data["percentage_scrapeable"]:.2f}%")
    print(f"Percentage scraped (total): {progress_data["percentage_scraped"]:.2f}%")
    print(f"Percentage scraped (from scrapeable): {progress_data["percentage_scraped_from_scrapeable"]:.2f}%")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_update_progress_file.py <state>")
        sys.exit(1)
    state = sys.argv[1]
    create_update_progress_file(state)
