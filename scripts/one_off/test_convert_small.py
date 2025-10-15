import os
import glob
import sys
from scripts.one_off.convert_to_people_schema import convert_to_people_schema

def convert_small_batch(delete_original=False):
    # Get first 5 files to test with
    yaml_files = glob.glob("data/**/people.yml", recursive=True)[:5]
    print(f"Testing conversion with {len(yaml_files)} files:")
    for f in yaml_files:
        print(f"  - {f}")
    print()
    
    if delete_original:
        print("⚠ WARNING: Original files will be DELETED after conversion!")
        print()
    
    # Use the main conversion function with specific files
    convert_to_people_schema(yaml_files, delete_original=delete_original)

if __name__ == "__main__":
    # Check for delete flag
    delete_original = "--delete-original" in sys.argv
    convert_small_batch(delete_original=delete_original)