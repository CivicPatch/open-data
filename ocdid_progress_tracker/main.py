import os
import json

def count_municipalities():
    # Resolve the absolute path to the data_source and google_data directories
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_source_path = os.path.join(project_root, "data_source")
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
                    name = m.get("name", "").lower().replace(" ", "_")
                    ocdid = f"ocd-division/country:us/state:{state.lower()}/place:{name}"
                    civicpatch_ocdids.add(ocdid)
                    civicpatch_names.add(name)
                    if m.get("website") and m.get("website").strip():
                        civicpatch_scrapeable_count += 1
                    # If meta_sources === [state_source, gemini, openai]
                    if len(m.get("meta_sources", [])) >= 3:
                        civicpatch_scraped_count += 1
        
        google_file = os.path.join(google_data_path, f"{state}_all_raw.json")
        google_count = 0
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
                    if ocdid.split("/")[-1].startswith("place:"):
                        google_count += 1
                        if ocdid not in civicpatch_ocdids:
                            missing_in_civicpatch.append({"ocdid": ocdid})
                # Identify OCD IDs in CivicPatch but not in Google
                for ocdid in civicpatch_ocdids:
                    if ocdid not in google_ocdids:
                        missing_in_google.append({"ocdid": ocdid})
        
        results.append({
            "state": state,
            "civicpatch_municipality_count": civicpatch_count,
            "civicpatch_scrapeable": civicpatch_scrapeable_count,
            "civicpatch_scraped": civicpatch_scraped_count,
            "civicpatch_scraped_percentage": round((civicpatch_scraped_count / civicpatch_scrapeable_count * 100), 2) if civicpatch_scrapeable_count > 0 else 0,
            "google_civics_municipality_count": google_count,
            "missing_in_civicpatch": missing_in_civicpatch,
            "missing_in_google": missing_in_google
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
