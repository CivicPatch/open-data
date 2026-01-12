from pathlib import Path
def jurisdiction_to_file(jurisdiction_ocdid):
    """Convert jurisdiction_ocdid to file path."""
    # Parse: ocd_jurisdiction/country:us/state:ca/county:green/place:anaheim/government
    parts = jurisdiction_ocdid.split("/")

    state = None
    county = None
    place = None
    jurisdiction_type = None

    for part in parts:
        if part.startswith("state:"):
            state = part.replace("state:", "")
        elif part.startswith("county:"):
            county = part.replace("county:", "")
        elif part.startswith("place:"):
            place = part.replace("place:", "")
    
    if not state:
        raise ValueError(f"No state found in: {jurisdiction_ocdid}")
    if not place:
        raise ValueError(f"No place found in: {jurisdiction_ocdid}")

    # Build file path
    if county:
        filename = f"county_{county}__place_{place}"
    else:
        filename = f"place_{place}"

    return Path(f"data/{state}/local/{filename}.yml")
