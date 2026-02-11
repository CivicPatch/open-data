import os
import argparse
import shutil
import yaml
import boto3
from urllib.parse import urlparse
import re

FRIENDLY_STORAGE_HOST = os.getenv("FRIENDLY_STORAGE_HOST")
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")
import scripts.utils as utils

def process_jurisdiction(jurisdiction_ocdid, data_file_path):
    print(f"Processing {jurisdiction_ocdid}..., with file {data_file_path}")
    # Get the data_source_folder from the data_file hierarchy, everything
    # is the same except for data_source vs data and the .yml file at the end

    data_source_folder = data_file_path.replace("data", "data_source").replace(".yml", "")

    update_images(data_file_path)

    create_update_config_file(data_file_path, data_source_folder)

def extract_s3_key_with_regex(cdn_image, source_bucket):
    """
    Extract the S3 object key from the cdn_image URL using regex.
    """
    # Match the pattern: https://{host}/{bucket}/{key}
    match = re.match(rf"https?://[^/]+/{source_bucket}/(.+)", cdn_image)
    if match:
        return match.group(1)  # Return the captured group (the key)
    return None

def update_images(yaml_file):
    # Load YAML data
    if not os.path.exists(yaml_file):
        print(f"YAML file {yaml_file} not found.")
        return

    with open(yaml_file, "r") as f:
        people = yaml.safe_load(f)

    updated = False

    # Setup boto3 client for S3-compatible storage
    s3 = boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=STORAGE_SECRET_ACCESS_KEY,
        region_name="auto"
    )

    source_bucket = "civicpatch-artifacts"
    dest_bucket = "civicpatch"

    for person in people:
        cdn_image = person.get("cdn_image")
        if not cdn_image or source_bucket not in cdn_image:
            continue

        # Extract the S3 key using regex
        input_key = extract_s3_key_with_regex(cdn_image, source_bucket)
        if not input_key:
            print(f"Could not extract key from URL: {cdn_image}")
            continue

        # Construct the output key
        # Extract the relevant part of the input key (removing the first two segments)
        key_parts = input_key.split('/')  # Split the input key into parts
        relevant_parts = key_parts[2:]  # Remove the first two segments (e.g., "2026-02-09-e530/data_source")
        # Construct the output key by prepending "open-data/" to the remaining path
        output_key = f"open-data/{'/'.join(relevant_parts)}"

        # Copy the object
        try:
            s3.copy_object(
                Bucket=dest_bucket,
                CopySource={"Bucket": source_bucket, "Key": input_key},
                Key=output_key,
            )
            print(f"Copied {input_key} from {source_bucket} to {dest_bucket} as {output_key}")
            # Delete the original object after successful copy
            #s3.delete_object(Bucket=source_bucket, Key=input_key)
            #print(f"Deleted {input_key} from {source_bucket}")
        except Exception as e:
            print(f"Failed to copy/delete {input_key}: {e}")
            continue

        # Update the cdn_image URL to the new bucket
        friendly_url = f"{FRIENDLY_STORAGE_HOST}/{output_key}"
        person["cdn_image"] = friendly_url
        updated = True

    # Write back only if changes were made
    if updated:
        with open(yaml_file, "w") as f:
            yaml.dump(people, f, sort_keys=False)

def create_update_config_file(data_file_path, data_source_folder):
    config_path = os.path.join(data_source_folder, "config.yml")

    # Load people data from YAML
    if not os.path.exists(data_file_path):
        print(f"Data file {data_file_path} not found.")
        return

    with open(data_file_path, "r") as f:
        data = yaml.safe_load(f)

    people = data.get("persons", []) if isinstance(data, dict) else []

    # Gather all source URLs and identities
    source_urls = []
    identities = []
    seen_names = set()
    offices = []

    for person in people:
        # Collect source URLs
        sources = person.get("sources", [])
        for src in sources:
            url = src.get("url")
            if url:
                source_urls.append(url)

        # Collect identities
        other_names = person.get("other_names", [])
        person_name = person.get("name")
        # Only add if other_names is non-empty and not already added
        filtered_other_names = [n.get("name") for n in other_names if n.get("name")]
        if filtered_other_names and person_name and person_name not in seen_names:
            seen_names.add(person_name)
            identities.append({
                "name": person_name,
                "other_names": filtered_other_names
            })
        offices.extend(person.get("office", {}))

    # Load or create config
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}

    config["source_urls"] = source_urls
    config["identities"] = identities
    config["offices"] = offices

    # Write back to config file
    with open(config_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a jurisdiction's files after a merge.")
    parser.add_argument("jurisdiction_ocdid", help="The OCDID of the jurisdiction to process.")
    args = parser.parse_args()
    process_jurisdiction(args.jurisdiction_ocdid)