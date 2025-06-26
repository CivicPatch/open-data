import json

def generate_readme(progress_file, output_file):
    with open(progress_file, "r") as file:
        data = json.load(file)

    # Static template with placeholders
    template = """# CivicPatch Open Data
# open-data

Every day at 9AM PST, this repo syncs the data/ and data_source/ folders from the
[civicpatch-tools repo](https://github.com/CivicPatch/civicpatch-tools)
    
## Progress Overview

All Google OCDIDs are gathered from these [set of files](https://drive.google.com/drive/folders/15DHdG3D4-IWeuAj5k-fTMUFVEkrYDGqn)

| State | CivicPatch Count | Scrapeable | Scraped | Scraped % | Google Count | Missing in CivicPatch | Missing in Google |
|-------|------------------|------------|---------|-----------|--------------|-----------------------|-------------------|
{progress_table}

## Missing OCD IDs by State

{missing_ocdids}

## Additional Information

- **Future Goals**:
    - [ ] Top 100 cities in Oregon
    - [ ] Top 100 cities in Colorado
    - [ ] Top 100 most populous cities in the US
"""

    # Generate the progress table dynamically
    progress_table = ""
    missing_ocdids = ""
    for state_data in data:
        state = state_data.get("state", "Unknown")
        civicpatch_count = state_data.get("civicpatch_municipality_count", 0)
        scrapeable = state_data.get("civicpatch_scrapeable", 0)
        scraped = state_data.get("civicpatch_scraped", 0)
        scraped_percentage = state_data.get("civicpatch_scraped_percentage", 0.0)
        google_count = state_data.get("google_civics_municipality_count", 0)
        missing_in_civicpatch = state_data.get("missing_in_civicpatch", [])
        missing_in_google = state_data.get("missing_in_google", [])

        # Add to the progress table
        progress_table += f"| {state} | {civicpatch_count} | {scrapeable} | {scraped} | {scraped_percentage:.2f}% | {google_count} | {len(missing_in_civicpatch)} | {len(missing_in_google)} |\n"

        # Add missing OCD IDs section
        missing_ocdids += f"### {state}\n\n"
        missing_ocdids += "**Missing in CivicPatch:**\n\n"
        if missing_in_civicpatch:
            for entry in missing_in_civicpatch:
                missing_ocdids += f"- {entry['ocdid']}\n"
        else:
            missing_ocdids += "None\n"

        missing_ocdids += "\n**Missing in Google:**\n\n"
        if missing_in_google:
            for entry in missing_in_google:
                missing_ocdids += f"- {entry['ocdid']}\n"
        else:
            missing_ocdids += "None\n"

        missing_ocdids += "\n"

    # Replace placeholders in the template
    readme_content = template.replace("{progress_table}", progress_table.strip())
    readme_content = readme_content.replace("{missing_ocdids}", missing_ocdids.strip())

    # Write the content to README.md
    with open(output_file, "w") as file:
        file.write(readme_content)

    print(f"README.md generated at {output_file}")

if __name__ == "__main__":
    progress_file = "/Users/michelle/CivicPatch/open-data/progress.json"
    output_file = "/Users/michelle/CivicPatch/open-data/README.md"
    generate_readme(progress_file, output_file)
