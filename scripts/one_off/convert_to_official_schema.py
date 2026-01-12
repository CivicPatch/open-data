import os
from pathlib import Path
import yaml
from schemas import Person, Official, Office

def person_to_official(person: Person) -> Official:
    return Official(
        name=person.name,

        phones=[person.phone_number] if person.phone_number else [],
        emails=[person.email] if person.email else [],
        urls=[person.website] if person.website else [],

        office=Office(
            name=" - ".join(person.roles),
            division_id=" - ".join(person.divisions) if person.divisions else None,
            start_date=person.start_date,
            end_date=person.end_date,
        ),
        
        image=person.image,

        jurisdiction_id=person.jurisdiction_id,
        cdn_image=person.cdn_image,
        source_urls=person.sources,
        updated_at=person.updated_at,
    )

def convert_people_to_officials(directory: str):
    """
    Traverse all YAML files under the given directory, convert Person schema to Official schema,
    and save the output back as YAML.

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

            # Convert each Person to Official
            officials = []
            for person_data in data:
                person = Person(**person_data)
                official = person_to_official(person)
                officials.append(official.dict())

            # Write the converted data back to the YAML file
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    officials,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            print(f"  ✓ Converted to Official schema: {file_path}")
            converted_count += 1

        except Exception as e:
            print(f"  ✗ Error processing file {file_path}: {e}")
            error_count += 1

    print("\nConversion complete!")
    print(f"Successfully converted: {converted_count} files")
    print(f"Errors: {error_count} files")

if __name__ == "__main__":
    root_folder = "data"
    script_folder = os.path.dirname(os.path.abspath(__file__))
    root_directory = os.path.join(script_folder, "..", "..", root_folder)
    convert_people_to_officials(root_directory)
