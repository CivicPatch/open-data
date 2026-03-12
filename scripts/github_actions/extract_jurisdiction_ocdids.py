import yaml
import sys

def extract_jurisdiction_ocdids(file_path: str) -> str | None:
    """Extract the jurisdiction_ocdid from a given YAML file.

    Args:
        file_path (str): The path to the YAML file, which is an array of People.

    Returns:
        str | None: The jurisdiction_ocdid of the first person entry if found, otherwise None.
    """
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
        if data and isinstance(data, list):
            return data[0].get('jurisdiction_ocdid', None)
        return None
    
if __name__ == "__main__":
    import sys
    if len(sys.argv) <= 1:
        print("Usage: python extract_jurisdiction_ocdids.py <file_path>,<file_path>")
        sys.exit(1)
    file_paths_arg = sys.argv[1:]
    #print(f"Received argument: {file_paths_arg}")
    file_paths = [path for path in file_paths_arg[0].split(",")]
    #print(f"Processing files: {file_paths}")
    ocdids = []
    for file_path in file_paths:
        ocdid = extract_jurisdiction_ocdids(file_path)
        if ocdid:
            ocdids.append(ocdid)
    print(",".join(ocdids))