#!/usr/bin/env python3
"""
Validate people data for a specific jurisdiction using the Pydantic model.

Usage:
    python scripts/validate_jurisdiction.py "ocd_jurisdiction/country:us/state:ca/place:anaheim/government"
    python scripts/validate_jurisdiction.py "ocd_jurisdiction/country:us/state:ca/county:green/place:anaheim/government"
"""

import sys
import yaml
from pathlib import Path
from schemas import Person


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
    
    return Path(f"data/{state}/{filename}")


def validate_file(file_path, jurisdiction_id):
    """Validate all people in a file."""
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
        
        people = data.get('government', data if isinstance(data, list) else [])
        valid_count = 0
        errors = []
        
        for i, person_data in enumerate(people):
            try:
                # Check jurisdiction_id matches
                if person_data.get('jurisdiction_id') != jurisdiction_id:
                    # Debugging: Print mismatch if jurisdiction_id does not match
                    print(f"Mismatch: Expected {jurisdiction_id}, Found {person_data.get('jurisdiction_id')}")
                    errors.append(f"Person {i+1}: Wrong jurisdiction_id")
                    continue
                
                Person(**person_data)  # Validate with Pydantic
                valid_count += 1
            except Exception as e:
                name = person_data.get('name', 'Unknown')
                errors.append(f"Person {i+1} ({name}): {e}")
        
        # Print results
        print(f"✅ Valid: {valid_count}")
        if errors:
            print(f"❌ Errors: {len(errors)}")
            for error in errors[:3]:  # Show first 3 errors
                print(f"   {error}")
            if len(errors) > 3:
                print(f"   ... and {len(errors) - 3} more errors")
            return False
        
        print("🎉 All people passed validation!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to process file: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_jurisdiction.py <jurisdiction_id>")
        return 1
    
    jurisdiction_id = sys.argv[1]
    
    try:
        file_path = jurisdiction_to_file(jurisdiction_id)
        print(f"📁 Checking: {file_path}")
        
        success = validate_file(file_path, jurisdiction_id)
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())