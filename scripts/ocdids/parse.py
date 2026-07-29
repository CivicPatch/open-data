from pathlib import Path
from typing import Optional
from pydantic import BaseModel

class JurisdictionId(BaseModel):
    country: str
    state: str
    county: Optional[str] = None
    place_label: str = "place"
    place: str
    jurisdiction_type: str
    output_type: str = "local"

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

def parse_jurisdiction_ocdid(jurisdiction_ocdid: str) -> JurisdictionId:
    """
    Parses a jurisdiction ID in the format
        "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
    OR
        "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government"
    and returns a JurisdictionId object.

    Returns None if the format is invalid.
    """
    try:
        components = jurisdiction_ocdid.split("/")
        result = {}
        country_part = components[1]
        result["country"] = country_part.split(":")[1]

        state_part = components[2]
        result["state"] = state_part.split(":")[1]

        substate_part = components[3]
        substate_label, substate_name = substate_part.split(":")
        if substate_label == "county":
            result["county"] = substate_name
            place_label, place_name = components[4].split(":")
            result["place_label"] = place_label
            result["place"] = place_name
        else:
            result["place_label"] = substate_label
            result["place"] = substate_name

        # Last component MUST contain the jurisdiction type
        # Which has no ":"
        jurisdiction_type = components[-1]
        if ":" in jurisdiction_type:
            raise ValueError("Invalid jurisdiction type format: contains ':'")

        if "country" not in result or "state" not in result:
            raise ValueError("Missing required jurisdiction components: country or state")
        
        return JurisdictionId(
            country=result["country"],
            state=result["state"],
            county=result.get("county", None),
            place_label=result["place_label"],
            place=result["place"],
            jurisdiction_type=jurisdiction_type,
            output_type="local" # Hardcasted as "local" for now
        )
    except Exception as e:
        raise ValueError(f"Invalid jurisdiction ID format: {jurisdiction_ocdid}, error: {e}") from e


def jurisdiction_ocdid_to_folder(jurisdiction_ocdid: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly folder name.
    Example:
      {
        country: "us",
        state: "il",
        county: "dupage", (optional)
        place: "naperville_test",
        jurisdiction_type: "government",
        output_type: "local"

      }
      -> "il/local/county_dupage__place_naperville_test"
    """

    jurisdiction_ocdid_parts = parse_jurisdiction_ocdid(jurisdiction_ocdid)

    folder = f"{jurisdiction_ocdid_parts.state}/{jurisdiction_ocdid_parts.output_type}/"
    if jurisdiction_ocdid_parts.county:
        folder += f"county_{jurisdiction_ocdid_parts.county}__"
    folder += f"{jurisdiction_ocdid_parts.place_label}_{jurisdiction_ocdid_parts.place}"

    return folder