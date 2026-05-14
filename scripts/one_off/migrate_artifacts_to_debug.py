#!/usr/bin/env python3
"""
One-off: copy all files from civicpatch-artifacts -> civicpatch-debug, skipping images/.

Requires env vars: STORAGE_ENDPOINT, STORAGE_ACCESS_KEY_ID, STORAGE_SECRET_ACCESS_KEY

Usage:
  uv run python scripts/one_off/migrate_artifacts_to_debug.py                    # dry run (default)
  uv run python scripts/one_off/migrate_artifacts_to_debug.py --execute
  uv run python scripts/one_off/migrate_artifacts_to_debug.py --execute --limit 50
"""
import os
import sys
import threading
import boto3
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed

EXECUTE = "--execute" in sys.argv

_limit_arg = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--limit" and i + 1 < len(sys.argv)), None)
LIMIT = int(_limit_arg) if _limit_arg else None

SOURCE_BUCKET = "civicpatch-artifacts"
DEST_BUCKET = "civicpatch-debug"
MAX_WORKERS = 32

_print_lock = threading.Lock()


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
    )


def iter_keys(s3, bucket):
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.startswith("images/") or "/images/" in key:
                continue
            yield key
            count += 1
            if LIMIT and count >= LIMIT:
                return


def copy_key(key):
    s3 = get_s3_client()
    try:
        s3.copy_object(
            CopySource={"Bucket": SOURCE_BUCKET, "Key": key},
            Bucket=DEST_BUCKET,
            Key=key,
        )
        return key, None
    except ClientError as e:
        return key, e


def main():
    s3 = get_s3_client()

    if not EXECUTE:
        print("Listing objects (dry run)...", flush=True)
        count = 0
        for key in iter_keys(s3, SOURCE_BUCKET):
            print(f"  [dry-run] {key}")
            count += 1
        print(f"\n{count} objects would be copied. Run with --execute to proceed.")
        return

    copied = 0
    failed = 0
    submitted = 0
    lock = threading.Lock()

    print("Starting copy (listing and copying in parallel)...", flush=True)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {}
        for key in iter_keys(s3, SOURCE_BUCKET):
            futures[pool.submit(copy_key, key)] = key
            submitted += 1

        for future in as_completed(futures):
            key, err = future.result()
            with lock:
                if err:
                    failed += 1
                    with _print_lock:
                        print(f"  FAILED: {key} — {err}", flush=True)
                else:
                    copied += 1
                    if copied % 100 == 0:
                        with _print_lock:
                            print(f"  [{copied}/{submitted}] copied so far...", flush=True)

    print(f"\nDone. {copied} copied, {failed} failed.")


if __name__ == "__main__":
    main()
