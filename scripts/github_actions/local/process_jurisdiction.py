import os
import argparse
import shutil
import yaml
import boto3
from urllib.parse import urlparse

FRIENDLY_STORAGE_HOST = os.getenv("FRIENDLY_STORAGE_HOST")
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")
import utils as utils

def process_jurisdiction(jurisdiction_ocdid):
    # Grab the data_source folder from the jurisdiction_ocdid
    jurisdiction_slug = utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)

    data_source_folder = os.path.join("data_source", jurisdiction_slug)
    data_file_path = os.path.join("data", jurisdiction_slug + ".yml")

    update_images(data_file_path)

    create_update_config_file(data_file_path, data_source_folder)

def update_images(yaml_file):
    # Load YAML data
    if not os.path.exists(yaml_file):
        print(f"YAML file {yaml_file} not found.")
        return

    with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)

    people = data.get("persons", []) if isinstance(data, dict) else []
    updated = False

    # Setup boto3 client for S3-compatible storage
    s3 = boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=STORAGE_SECRET_ACCESS_KEY,
    )

    for person in people:
        cdn_image = person.get("cdn_image")
        if not cdn_image:
            continue

        # Only process images in the civicpatch-pr-images bucket
        if "civicpatch-pr-images" in cdn_image:
            # Parse the URL to get the key
            parsed = urlparse(cdn_image)
            # Remove leading slash from path
            key = parsed.path.lstrip("/")
            source_bucket = "civicpatch-pr-images"
            dest_bucket = "civicpatch"

            # Copy the object
            try:
                s3.copy_object(
                    Bucket=dest_bucket,
                    CopySource={"Bucket": source_bucket, "Key": key},
                    Key=key,
                )
                print(f"Copied {key} from {source_bucket} to {dest_bucket}")
                # Delete the original object after successful copy
                s3.delete_object(Bucket=source_bucket, Key=key)
                print(f"Deleted {key} from {source_bucket}")
            except Exception as e:
                print(f"Failed to copy/delete {key}: {e}")
                continue

            # Update the cdn_image URL to the new bucket
            new_url = cdn_image.replace("civicpatch-pr-images", "civicpatch")
            person["cdn_image"] = new_url
            updated = True

    # Write back only if changes were made
    if updated:
        with open(yaml_file, "w") as f:
            yaml.dump(data, f, sort_keys=False)

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