from schemas import Person
import glob
import yaml
import os
from pathlib import Path
from datetime import datetime, timezone
import sys


def convert_to_people_schema(file_paths=None, delete_original=False):
    """
    Convert people.yml files to new schema format.

    Args:
        file_paths: List of specific file paths to convert. If None, converts all people.yml files.
        delete_original: If True, delete the original people.yml files after successful conversion.
    """
    # 1. Get files to convert
    if file_paths is None:
        # Convert all files
        yaml_files = glob.glob("data/**/people.yml", recursive=True)
        print(f"Found {len(yaml_files)} people.yml files to convert")
    else:
        # Convert only specified files
        yaml_files = file_paths
        print(f"Converting {len(yaml_files)} specified files")

    converted_count = 0
    error_count = 0

    for file_path in yaml_files:
        try:
            # 2. For each file, load the YAML content and take note of the current file path
            print(f"Processing: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Extract state and place name from path: data/state/place/people.yml
            path_parts = Path(file_path).parts
            state = path_parts[1]  # e.g., 'ca', 'or', 'wa'
            place = path_parts[2]  # e.g., 'gervais', 'kenmore'

            # 3. Validate and convert the content to the Person schema
            validated_people = []

            for person_data in data:
                # Add missing required fields
                person_data["jurisdiction_ocdid"] = (
                    f"ocd-jurisdiction/country:us/state:{state}/place:{place}/government"
                )

                # Ensure required fields exist
                if "divisions" not in person_data or not person_data["divisions"]:
                    person_data["divisions"] = ["City"]

                if "cdn_image" not in person_data or not person_data["cdn_image"]:
                    person_data["cdn_image"] = ""

                if "sources" not in person_data or not person_data["sources"]:
                    person_data["sources"] = []

                if "updated_at" not in person_data or not person_data["updated_at"]:
                    person_data["updated_at"] = datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    )
                else:
                    # Ensure 'updated_at' is in the correct format or reset missing time to 12:00 AM
                    if "updated_at" in person_data:
                        try:
                            # Parse the existing date
                            parsed_date = datetime.strptime(
                                person_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
                            )
                            # Reformat to the required format
                            person_data["updated_at"] = parsed_date.replace(
                                tzinfo=timezone.utc
                            ).isoformat(timespec="seconds")
                        except ValueError:
                            # If time is missing, reset to 12:00 AM
                            try:
                                parsed_date = datetime.strptime(
                                    person_data["updated_at"], "%Y-%m-%d"
                                )
                                parsed_date = parsed_date.replace(
                                    hour=0, minute=0, second=0, tzinfo=timezone.utc
                                )
                                person_data["updated_at"] = parsed_date.isoformat(
                                    timespec="seconds"
                                )
                            except ValueError:
                                raise ValueError(
                                    f"DateTime must be in format '2025-10-19T23:31:54+00:00', got: '{person_data['updated_at']}'"
                                )

                # Ensure 'start_date' and 'end_date' are not '.'; set to null if so
                for date_field in ["start_date", "end_date"]:
                    if date_field in person_data and person_data[date_field] == ".":
                        person_data[date_field] = None

                # Validate using Pydantic schema
                person = Person(**person_data)

                # Convert to ordered dict maintaining Pydantic model field order
                person_dict = {}
                for field_name in Person.model_fields:
                    person_dict[field_name] = getattr(person, field_name)

                validated_people.append(person_dict)

            # 4. Save the converted content to a new file under data/<state>/place_<place_name>.yml
            output_path = f"data/{state}/place_{place}.yml"

            # The people list should be nested under the key: government
            output_data = {"government": validated_people}

            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    output_data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            print(f"  ✓ Converted {len(validated_people)} people to {output_path}")
            converted_count += 1

        except Exception as e:
            print(f"  ✗ Error processing {file_path}: {e}")
            error_count += 1
            continue  # Skip to next file, don't delete this one

        # Only delete if we reach here (no exceptions occurred)
        if delete_original:
            try:
                os.remove(file_path)
                print(f"  ✓ Deleted original file: {file_path}")

                # Try to remove parent directory if it's empty
                parent_dir = os.path.dirname(file_path)
                try:
                    os.rmdir(parent_dir)  # Only works if directory is empty
                    print(f"  ✓ Deleted empty directory: {parent_dir}")
                except OSError:
                    # Directory not empty or other error - this is fine, just ignore
                    pass

            except Exception as delete_error:
                print(f"  ⚠ Warning: Could not delete {file_path}: {delete_error}")

    print(f"\nConversion complete!")
    print(f"Successfully converted: {converted_count} files")
    print(f"Errors: {error_count} files")


if __name__ == "__main__":
    # Parse command line arguments
    delete_original = False
    file_paths = []

    for arg in sys.argv[1:]:
        if arg == "--delete-original":
            delete_original = True
        else:
            file_paths.append(arg)

    # If file paths provided, use those; otherwise convert all files
    if file_paths:
        convert_to_people_schema(file_paths, delete_original=delete_original)
    else:
        # No file paths specified, convert all files
        convert_to_people_schema(delete_original=delete_original)
