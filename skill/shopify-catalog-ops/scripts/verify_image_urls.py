#!/usr/bin/env python3
"""
Public Image URL Verifier Helper
================================
Concurrently verifies that image URLs referenced in a Shopify import CSV are
publicly accessible (HTTP 200 OK) before running an import.

Usage:
    python verify_image_urls.py [import_csv_path] [--threads 10]
"""

import sys
import csv
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_url(url, timeout=10):
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return url, resp.status == 200, resp.status
    except urllib.error.HTTPError as e:
        return url, False, e.code
    except Exception as e:
        return url, False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Verify image URLs in a Shopify import CSV.")
    parser.add_argument("csv_file", help="Path to Shopify import CSV")
    parser.add_argument("--threads", type=int, default=10, help="Number of concurrent worker threads")
    args = parser.parse_args()

    urls_to_check = set()
    with open(args.csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        img_col = None
        for col in ["Image Src", "Product image URL", "Variant image URL"]:
            if col in reader.fieldnames:
                img_col = col
                break
        
        if not img_col:
            print(f"No image column found in {args.csv_file}. Columns: {reader.fieldnames}")
            sys.exit(0)

        for row in reader:
            val = (row.get(img_col) or "").strip()
            if val and val.startswith("http"):
                urls_to_check.add(val)

    print(f"Found {len(urls_to_check)} unique image URLs in {args.csv_file}.")
    if not urls_to_check:
        return

    failed = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(check_url, u): u for u in urls_to_check}
        for future in as_completed(futures):
            url, ok, status = future.result()
            if not ok:
                failed.append((url, status))
                print(f" [FAIL] ({status}) {url}")
            else:
                print(f" [OK] {url}")

    print("\n--- Summary ---")
    print(f"Total checked : {len(urls_to_check)}")
    print(f"Successful    : {len(urls_to_check) - len(failed)}")
    print(f"Failed        : {len(failed)}")

    if failed:
        sys.exit(1)
    else:
        print("All image URLs are publicly reachable.")
        sys.exit(0)

if __name__ == "__main__":
    main()
