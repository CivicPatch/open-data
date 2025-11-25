from pathlib import Path
def jurisdiction_to_file(jurisdiction_id):
    """Convert jurisdiction_id to file path."""
    # Parse: ocd_jurisdiction/country:us/state:ca/county:green/place:anaheim/government
    parts = jurisdiction_id.split("/")

    state = None
    county = None
    place = None

    for part in parts:
        if part.startswith("state:"):
            state = part.replace("state:", "")
        elif part.startswith("county:"):
            county = part.replace("county:", "")
        elif part.startswith("place:"):
            place = part.replace("place:", "")

    if not state:
        raise ValueError(f"No state found in: {jurisdiction_id}")
    if not place:
        raise ValueError(f"No place found in: {jurisdiction_id}")

    # Build file path
    if county:
        filename = f"county_{county}__place_{place}.yml"
    else:
        filename = f"place_{place}.yml"

    return Path(f"data/{state}/local/{filename}")
