import sys
from pathlib import Path

import yaml

from scripts.paths import PROJECT_ROOT
def count_jurisdictions(state: str):
    print("Counting jurisdictions...")
    jurisdictions_file_path = PROJECT_ROOT / "data_source" / state / "jurisdictions.yml"
    jurisdictions_data = yaml.safe_load(
        jurisdictions_file_path.read_text(encoding="utf-8")
    )

    num_jurisdictions = len(jurisdictions_data["jurisdictions"])
    print(f"Number of jurisdictions in {state}: {num_jurisdictions}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/count_jurisdictions.py <state>")
        sys.exit(1)
    state = sys.argv[1]
    count_jurisdictions(state)
