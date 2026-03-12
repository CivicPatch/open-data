import os
import sys
import yaml


def process_files(file_list):
    files = file_list.split()

    for file_path in files:
        # Ensure the file is in the expected directory and format
        if not file_path.startswith("data/") or not file_path.endswith(".yml"):
            print(f"Skipping invalid file: {file_path}")
            continue

        # Extract state and place/county_and_place
        parts = file_path.split("/")
        if len(parts) != 3:
            print(f"Skipping unexpected file structure: {file_path}")
            continue

        _, state, file_name = parts
        place = os.path.splitext(file_name)[0]  # Remove the .yml extension

        # Process the file (e.g., load YAML, convert, etc.)
        print(f"Processing file: {file_path}")
        print(f"  State: {state}")
        print(f"  FIle: {place}")

        # Example: Load YAML and print its contents
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
                print(f"  YAML Data: {data}")
        except Exception as e:
            print(f"  Error reading {file_path}: {e}")

        # Extract jurisdiction ids under


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_files.py '<file1> <file2> ...'")
        sys.exit(1)

    file_list = sys.argv[1]
    process_files(file_list)
