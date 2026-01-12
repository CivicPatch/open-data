import json
import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent


def count_municipalities():
    # Resolve the absolute path to the data_source and google_data directories
    data_source_path = os.path.join(PROJECT_ROOT, "data_source")
    google_data_path = os.path.join(
        PROJECT_ROOT, "scripts", "track_progress", "google_data"
    )

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
        progress_file = os.path.join(state_path, "jurisdictions_metadata.yml")

        # Skip states without government_progress.yml
        if not os.path.isfile(progress_file):
            print(f"Skipping {state}: jurisdictions_metadata.yml not found.")
            continue

        civicpatch_ocdids = set()
        civicpatch_hyperlocal_divisions = set()
        civicpatch_count = 0
        civicpatch_scrapeable_count = 0
        civicpatch_scraped_count = 0

        # Load government_progress.yml
        with open(progress_file, "r") as file:
            progress_data = yaml.safe_load(file)
            jurisdictions_by_id = progress_data.get("jurisdictions_by_id", {})
            civicpatch_count = progress_data.get("num_jurisdictions", 0)
            civicpatch_scrapeable_count = progress_data.get(
                "num_jurisdictions_with_urls", 0
            )
            civicpatch_scraped_count = (
                int(
                    progress_data.get("percentage_scraped_from_scrapeable", 0)
                    * civicpatch_scrapeable_count
                    / 100
                )
                if civicpatch_scrapeable_count
                else 0
            )

            for jurisdiction_ocdid, jurisdiction_obj in jurisdictions_by_id.items():
                # Chop off /government for comparison
                base_ocdid = jurisdiction_ocdid.replace("/government", "")
                civicpatch_ocdids.add(base_ocdid)
                # Add child divisions
                for division in jurisdiction_obj.get("child_divisions", []):
                    civicpatch_hyperlocal_divisions.add(division)

        google_file = os.path.join(google_data_path, f"{state}_all_raw.json")
        google_civics_hyperlocal_divisions = set()
        missing_in_civicpatch = []  # OCD IDs in Google but not in CivicPatch
        missing_in_google = []  # OCD IDs in CivicPatch but not in Google
        if os.path.isfile(google_file):
            with open(google_file, "r") as file:
                data = json.load(file)
                divisions = data.get("divisions", {})
                print(f"Processing {len(divisions)} divisions for state: {state}")
                google_ocdids = set()
                for ocdid in divisions.keys():
                    # Get base place ocdid for comparison
                    parts = ocdid.split("/")
                    place_idx = [
                        i for i, p in enumerate(parts) if p.startswith("place:")
                    ]
                    if place_idx:
                        base_ocdid = "/".join(parts[: place_idx[0] + 1])
                        google_ocdids.add(base_ocdid)
                        # Only count if it's a place:* division (not hyperlocal)
                    # Hyperlocal division
                    if any(
                        p.startswith("council_district:") or p.startswith("ward:")
                        for p in parts
                    ):
                        google_civics_hyperlocal_divisions.add(ocdid)

                # Normalize for comparison
                norm_civicpatch_ocdids = set(
                    normalize_ocdid(o) for o in civicpatch_ocdids
                )
                norm_google_ocdids = set(normalize_ocdid(o) for o in google_ocdids)

                # Identify OCD IDs in Google but not in CivicPatch
                missing_in_civicpatch = []
                for ocdid in norm_google_ocdids:
                    if ocdid not in norm_civicpatch_ocdids:
                        missing_in_civicpatch.append({"ocdid": ocdid})

                # Identify OCD IDs in CivicPatch but not in Google
                missing_in_google = []
                for ocdid in norm_civicpatch_ocdids:
                    if ocdid not in norm_google_ocdids:
                        missing_in_google.append({"ocdid": ocdid})

                # For hyperlocal divisions
                norm_civicpatch_hyperlocal_divisions = set(
                    normalize_ocdid(d) for d in civicpatch_hyperlocal_divisions
                )
                norm_google_civics_hyperlocal_divisions = set(
                    normalize_ocdid(d) for d in google_civics_hyperlocal_divisions
                )

                missing_in_civicpatch_divisions = (
                    norm_google_civics_hyperlocal_divisions
                    - norm_civicpatch_hyperlocal_divisions
                )
                missing_in_google_divisions = (
                    norm_civicpatch_hyperlocal_divisions
                    - norm_google_civics_hyperlocal_divisions
                )

                results.append(
                    {
                        "state": state,
                        "civicpatch_municipality_count": civicpatch_count,
                        "civicpatch_scrapeable": civicpatch_scrapeable_count,
                        "civicpatch_scraped": civicpatch_scraped_count,
                        "civicpatch_scraped_percentage": round(
                            (
                                civicpatch_scraped_count
                                / civicpatch_scrapeable_count
                                * 100
                            ),
                            2,
                        )
                        if civicpatch_scrapeable_count > 0
                        else 0,
                        "civicpatch_hyperlocal_divisions_count": len(
                            civicpatch_hyperlocal_divisions
                        ),
                        "google_civics_hyperlocal_divisions_count": len(
                            google_civics_hyperlocal_divisions
                        ),
                        "google_civics_municipality_count": len(norm_google_ocdids),
                        "missing_in_civicpatch": {
                            "places": missing_in_civicpatch,
                            "divisions": sorted(list(missing_in_civicpatch_divisions)),
                        },
                        "missing_in_google": {
                            "places": missing_in_google,
                            "divisions": sorted(list(missing_in_google_divisions)),
                        },
                    }
                )

    # Write results to a JSON file
    output_file = os.path.join(PROJECT_ROOT, "progress.json")
    with open(output_file, "w") as outfile:
        json.dump(results, outfile, indent=4)

    print(f"Results written to {output_file}")
    print("Municipality comparison results:")
    for result in results:
        print(
            f"State: {result['state']}, CivicPatch: {result['civicpatch_municipality_count']}, Google Civics: {result['google_civics_municipality_count']}"
        )


def normalize_ocdid(ocdid):
    # Remove ocd-division/ or ocd-jurisdiction/ prefix
    if ocdid.startswith("ocd-division/"):
        return ocdid[len("ocd-division/") :]
    elif ocdid.startswith("ocd-jurisdiction/"):
        return ocdid[len("ocd-jurisdiction/") :]
    return ocdid


if __name__ == "__main__":
    count_municipalities()
