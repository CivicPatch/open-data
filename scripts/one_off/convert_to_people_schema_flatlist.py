import os
import json
import yaml


def remove_government_key_and_flatten(directory: str):
    """
    Traverse all YAML files under the given directory, remove the "government" key,
    and promote its contents to the top level. Convert the files to flat JSON.

    Args:
        directory (str): The root directory to search for YAML files.
    """
    # Walk through the directory and find all .yml files
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".yml"):
                file_path = os.path.join(root, file)
                print(f"Processing file: {file_path}")

                try:
                    # Load the YAML file
                    with open(file_path, "r") as f:
                        data = yaml.safe_load(f)

                    # Check if the "government" key exists
                    if "government" in data:
                        # Promote the contents of "government" to the top level
                        data = data["government"]

                    # Convert the data to JSON
                    json_output = json.dumps(data, indent=2)

                    # Write the JSON output back to the file
                    with open(file_path, "w") as f:
                        f.write(json_output)

                    print(f"Updated file: {file_path}")

                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")


if __name__ == "__main__":
    # Define the root directory containing the YAML files
    root_directory = "data"

    # Run the script
    remove_government_key_and_flatten(root_directory)
