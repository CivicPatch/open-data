"""
Apply Cache-Control headers to existing maps/*.pmtiles objects in R2.

Run once after generate_pmtiles.py is updated; new uploads will set the header
themselves, so this script is only needed to update files already in R2.

    uv run python scripts/one_off/update_pmtiles_cache_headers.py
"""

import os
import sys

import boto3

CACHE_CONTROL = "public, max-age=3600, s-maxage=86400"
BUCKET = "civicpatch"
PREFIX = "maps/"


def main() -> int:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
    )

    paginator = s3.get_paginator("list_objects_v2")
    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX)
        for obj in page.get("Contents", [])
        if obj["Key"].endswith(".pmtiles")
    ]

    if not keys:
        print(f"No .pmtiles objects found under {BUCKET}/{PREFIX}")
        return 0

    print(f"Updating Cache-Control on {len(keys)} object(s)...")
    for key in keys:
        s3.copy_object(
            Bucket=BUCKET,
            Key=key,
            CopySource={"Bucket": BUCKET, "Key": key},
            ContentType="application/octet-stream",
            CacheControl=CACHE_CONTROL,
            MetadataDirective="REPLACE",
        )
        print(f"  ✓ {key}")

    print(f"Done. Cache-Control set to: {CACHE_CONTROL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
