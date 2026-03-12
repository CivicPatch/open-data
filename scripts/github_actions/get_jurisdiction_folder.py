import sys
import os
from scripts.utils import jurisdiction_ocdid_to_folder

def get_jurisdiction_folder(jurisdiction_ocdid: str) -> str:
    """
    Given a jurisdiction_ocdid, return the corresponding jurisdiction folder path.
    Assumes the folder structure is data/{state}/{jurisdiction_folder}/
    where jurisdiction_folder is derived from the last part of the ocdid.
    """

    return jurisdiction_ocdid_to_folder(jurisdiction_ocdid)

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python get_jurisdiction_folder.py <jurisdiction_ocdid>")
        sys.exit(1)

    jurisdiction_ocdid = sys.argv[1]
    folder_path = get_jurisdiction_folder(jurisdiction_ocdid)
    print(folder_path)