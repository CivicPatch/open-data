import os
import yaml
from pathlib import Path


def flatten_government_key_and_convert_to_yaml(directory: str):
    """
    Traverse all YAML files under the given directory, remove the "government" key,
    and promote its contents to the top level. Save the output back as YAML.

    Args:
        directory (str): The root directory to search for YAML files.
    """
    # Walk through the directory and find all .yml files
    yaml_files = list(Path(directory).rglob("*.yml"))
    print(f"Found {len(yaml_files)} YAML files to process.")

    converted_count = 0
    error_count = 0

    for file_path in yaml_files:
        try:
            file_path = str(file_path)  # Convert Path object to string
            print(f"Processing file: {file_path}")

            # Load the YAML file
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Check if the "government" key exists and promote its contents
            if "government" in data:
                data = data["government"]

            # Write the flattened data back to the YAML file
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            print(f"  ✓ Converted to YAML: {file_path}")
            converted_count += 1

        except Exception as e:
            print(f"  ✗ Error processing file {file_path}: {e}")
            error_count += 1

    print("\nConversion complete!")
    print(f"Successfully converted: {converted_count} files")
    print(f"Errors: {error_count} files")


if __name__ == "__main__":
    # Default root directory
    root_directory = "data"

    # Run the script
    flatten_government_key_and_convert_to_yaml(root_directory)
