import os
import json

def count_municipalities():
    # Resolve the absolute path to the data_source directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_source_path = os.path.join(project_root, "data_source")
    google_data_path = os.path.join(project_root, "ocdid_progress_tracker/google_data")  # Assuming Google data is stored here
    
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
        if os.path.isfile(municipalities_file):
            with open(municipalities_file, "r") as file:
                data = json.load(file)
                civicpatch_count = len(data.get("municipalities", []))
        
        google_file = os.path.join(google_data_path, state, "municipalities.json")
        google_count = 0
        if os.path.isfile(google_file):
            with open(google_file, "r") as file:
                data = json.load(file)
                google_count = len(data.get("municipalities", []))
        
        results.append({
            "state": state,
            "civicpatch_municipality_count": civicpatch_count,
            "google_civics_municipality_count": google_count
        })
    
    # Write results to a JSON file
    #output_file = os.path.join(project_root, "municipality_comparison.json")
    #with open(output_file, "w") as outfile:
    #    json.dump(results, outfile, indent=4)
    
    #print(f"Results written to {output_file}")
    print("Municipality comparison results:")
    for result in results:
        print(f"State: {result['state']}, CivicPatch: {result['civicpatch_municipality_count']}, Google Civics: {result['google_civics_municipality_count']}")  

if __name__ == "__main__":
    count_municipalities()
