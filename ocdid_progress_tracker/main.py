import os
import json
import yaml

def count_municipalities():
    # Resolve the absolute path to the data_source and google_data directories
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_source_path = os.path.join(project_root, "data_source")
    data_path = os.path.join(project_root, "data")
    google_data_path = os.path.join(project_root, "ocdid_progress_tracker/google_data")
    
    print(f"Resolved data source path: {data_source_path}")
    print(f"Resolved Google data path: {google_data_path}")
    
    if not os.path.exists(data_source_path):
        print("Data source directory does not exist.")
        return
    
    if not os.path.exists(google_data_path):
        print("Google data directory does not exist.")
        return
    
    results = []
    
    for state in os.listdir(data_source_path):
        state_path = os.path.join(data_source_path, state)
        municipalities_file = os.path.join(state_path, "municipalities.json")
        
        civicpatch_count = 0
        civicpatch_scrapeable_count = 0
        civicpatch_scraped_count = 0
        civicpatch_ocdids = set()
        civicpatch_names = set()
        if os.path.isfile(municipalities_file):
            with open(municipalities_file, "r") as file:
                data = json.load(file)
                municipalities = data.get("municipalities", [])
                civicpatch_count = len(municipalities)
                # Generate OCD IDs for CivicPatch names
                for m in municipalities:
                    hardcoded_ocdid = m.get("ocdid")
                    name = m.get("name", "").lower().replace(" ", "_")
                    ocdid = hardcoded_ocdid or f"ocd-division/country:us/state:{state.lower()}/place:{name}"
                    civicpatch_ocdids.add(ocdid)
                    civicpatch_names.add(name)
                    if m.get("website") and m.get("website").strip():
                        civicpatch_scrapeable_count += 1
                    # If meta_sources === [state_source, gemini, openai]
                    if len(m.get("meta_sources", [])) >= 3:
                        civicpatch_scraped_count += 1
        
        google_file = os.path.join(google_data_path, f"{state}_all_raw.json")
        google_count = 0
        google_civics_hyperlocal_divisions = set()
        missing_in_civicpatch = []  # OCD IDs in Google but not in CivicPatch
        missing_in_google = []  # OCD IDs in CivicPatch but not in Google
        if os.path.isfile(google_file):
            with open(google_file, "r") as file:
                data = json.load(file)
                divisions = data.get("divisions", {})
                print(f"Processing {len(divisions)} divisions for state: {state}")
                google_ocdids = set(divisions.keys())
                for ocdid in google_ocdids:
                    # Ensure the OCD ID ends with place:<name>
                    division_type = ocdid.split("/")[-1]
                    if division_type.startswith("place:"):
                        google_count += 1
                        if ocdid not in civicpatch_ocdids:
                            missing_in_civicpatch.append({"ocdid": ocdid})
                    elif division_type.startswith("ward:") or division_type.startswith("council_district:"):
                        has_place = ocdid.startswith(f"ocd-division/country:us/state:{state.lower()}/place:")
                        if has_place:
                            google_civics_hyperlocal_divisions.add(ocdid)

                # Identify OCD IDs in CivicPatch but not in Google
                for ocdid in civicpatch_ocdids:
                    if ocdid not in google_ocdids:
                        missing_in_google.append({"ocdid": ocdid})

        # Under the data folder, for every folder under the state except for .maps,
        # grab the people.yml file
        civicpatch_hyperlocal_divisions = set()
        for municipality_folder in os.listdir(os.path.join(data_path, state)):
            if municipality_folder.startswith("."):
                continue
            people_file = os.path.join(data_path, state, municipality_folder, "people.yml")
            if os.path.isfile(people_file):
                with open(people_file, "r") as file:
                    people_data = yaml.safe_load(file)
                    for person in people_data:
                        divisions = person.get("divisions", [])
                        if not divisions:
                            continue
                        for division in divisions:
                            name = municipality_folder.split("_")[0]
                            formatted_division = division.replace(" ", ":").lower()
                            formatted_division = formatted_division.replace("district", "council_district")
                            ocdid = "ocd-division/country:us/state:{state}/place:{name}/{division}".format(state=state.lower(), name=name, division=formatted_division)
                            # Check if the OCD ID is a hyperlocal division for the state
                            if formatted_division.startswith("council_district:") or formatted_division.startswith("ward:"):
                                civicpatch_hyperlocal_divisions.add(ocdid)

        missing_in_civicpatch_divisions = google_civics_hyperlocal_divisions - civicpatch_hyperlocal_divisions
        missing_in_google_divisions = civicpatch_hyperlocal_divisions - google_civics_hyperlocal_divisions

        results.append({
            "state": state,
            "civicpatch_municipality_count": civicpatch_count,
            "civicpatch_scrapeable": civicpatch_scrapeable_count,
            "civicpatch_scraped": civicpatch_scraped_count,
            "civicpatch_scraped_percentage": round((civicpatch_scraped_count / civicpatch_scrapeable_count * 100), 2) if civicpatch_scrapeable_count > 0 else 0,
            "civicpatch_hyperlocal_divisions_count": len(civicpatch_hyperlocal_divisions),
            "google_civics_hyperlocal_divisions_count": len(google_civics_hyperlocal_divisions),
            "google_civics_municipality_count": google_count,
            "missing_in_civicpatch": {
                "places": missing_in_civicpatch,
                "divisions": sorted(list(missing_in_civicpatch_divisions))
            },
            "missing_in_google": {
                "places": missing_in_google,
                "divisions": sorted(list(missing_in_google_divisions))
            }
        }) 
    
    # Write results to a JSON file
    output_file = os.path.join(project_root, "progress.json")
    with open(output_file, "w") as outfile:
        json.dump(results, outfile, indent=4)
    
    print(f"Results written to {output_file}")
    print("Municipality comparison results:")
    for result in results:
        print(f"State: {result['state']}, CivicPatch: {result['civicpatch_municipality_count']}, Google Civics: {result['google_civics_municipality_count']}")  

if __name__ == "__main__":
    count_municipalities()
