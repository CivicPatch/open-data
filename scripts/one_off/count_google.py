import os
import json
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def count_google_place_jurisdictions():
    google_file = os.path.join(PROJECT_PATH, "scripts", "track_progress", "google_data", "tx_all_processed.json")
    place_set = set()
    with open(google_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for entry in data:
        if isinstance(entry, dict):
            div_id = entry.get("office_divisionId", "")
            # Extract place:<name> from divisionId
            match = div_id.split("/place:")
            if len(match) > 1:
                place = match[1].split("/")[0]
                place_set.add(place)
    return len(place_set)

if __name__ == "__main__":
    count = count_google_place_jurisdictions()
    print(f"Count of unique place jurisdictions in Google data: {count}")
