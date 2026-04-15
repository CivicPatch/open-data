import os
import boto3
import re
from botocore.exceptions import ClientError

FRIENDLY_STORAGE_HOST = os.getenv("FRIENDLY_STORAGE_HOST")
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")

def process_jurisdiction(jurisdiction_ocdid, data_file_path, people):
    print("Processing jurisdiction:", jurisdiction_ocdid)
    if not os.path.exists(data_file_path):
        print(f"YAML file {data_file_path} not found.")
        return people, False

    updated = update_images(people)
    return people, updated

def extract_s3_key_with_regex(cdn_image, source_bucket):
    """
    Extract the S3 object key from the cdn_image URL using regex.
    """
    # Match the pattern: https://{bucket-as-subdomain}.host/{key}
    match = re.match(rf"https?://{re.escape(source_bucket)}[^/]*/(.+)", cdn_image)
    if match:
        return match.group(1)  # Return the captured group (the key)
    return None

def update_images(people) -> bool:
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
        if not isinstance(person, dict):
            continue
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
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("NoSuchKey", "404"):
                print(f"WARNING: image not found in {source_bucket}, skipping: {input_key}")
            else:
                print(f"WARNING: failed to copy {input_key} ({code}): {e}")
            continue

        # Update the cdn_image URL to the new bucket
        friendly_url = f"{FRIENDLY_STORAGE_HOST}/{output_key}"
        person["cdn_image"] = friendly_url
        updated = True

    return updated
