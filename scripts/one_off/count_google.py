import os
import json
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def count_google():
    google_file = os.path.join(PROJECT_PATH, "scripts", "track_progress", "google_data", "tx_all_processed.json")
    with open(google_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    filtered_for_place = [entry for entry in data if isinstance(entry, dict) and "/place:" in entry.get("office_divisionId", "")]
    return len(filtered_for_place)

if __name__ == "__main__":
    count = count_google()
    print(f"Count of officials in Google data: {count}")
