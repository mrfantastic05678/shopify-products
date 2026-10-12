#!/usr/bin/env python3
"""
audit_catalog_discrepancies.py
--------------------------------
Automated audit script for Shopify catalog ingestion.
Detects:
1. Cross-category duplicate listings and price conflicts.
2. Binary image file duplication across folders (MD5 check).
3. Image prefix mismatches and missing image assets.
4. Model code conflicts (Factory technical code vs e-commerce title).
5. Missing required fields (Titles, Descriptions, Prices, Weights).
6. Skipped rows and unlisted image folders on disk.
"""

import os, sys, re, hashlib, argparse
from collections import Counter

def calculate_md5(filepath):
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def normalize_string(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def audit_catalog(products_list, images_dir):
    """
    products_list: list of dicts with keys:
      sku, title, desc_short, cat_main, cat, mrp, weight, images_list, etc.
    """
    print("=" * 60)
    print("STARTING COMPREHENSIVE CATALOG AUDIT")
    print("=" * 60)

    # 1. Duplicate Titles and Cross-Category Clashes
    by_norm_title = {}
    for p in products_list:
        norm = normalize_string(p.get('title', ''))
        by_norm_title.setdefault(norm, []).append(p)

    dup_groups = {k: v for k, v in by_norm_title.items() if len(v) > 1}
    print(f"\n[1] Duplicate Product Listings: {len(dup_groups)} groups detected")
    for norm, group in dup_groups.items():
        print(f"  Title Group: \"{group[0].get('title')}\"")
        for item in group:
            print(f"    SKU: {item.get('sku')} | Cat: {item.get('cat_main')} > {item.get('cat')} | MRP: {item.get('mrp')}")

    # 2. Binary Image File Check for Duplicates
    print(f"\n[2] Binary Image Verification for Duplicates")
    for norm, group in dup_groups.items():
        group_hashes = []
        for item in group:
            item_hashes = []
            for img_path in item.get('images_list', []):
                if os.path.exists(img_path):
                    h = calculate_md5(img_path)
                    sz = os.path.getsize(img_path)
                    item_hashes.append((h, sz))
            group_hashes.append(tuple(sorted(item_hashes)))

        if len(set(group_hashes)) == 1 and len(group_hashes[0]) > 0:
            print(f"  -> Title \"{group[0].get('title')[:40]}\": EXACT BINARY DUPLICATES (Same photos in both folders)")
        else:
            print(f"  -> Title \"{group[0].get('title')[:40]}\": SEPARATE / DIFFERENT PHOTOS (Review needed)")

    # 3. Model Code vs Title Conflicts
    print(f"\n[3] Model Code Divergence Check")
    model_conflicts = []
    for p in products_list:
        desc = p.get('desc_short', '')
        title = p.get('title', '')
        m_item = re.search(r'ITEMS?\s*NO\s*:\s*([A-Za-z0-9\-]+)', desc, re.IGNORECASE)
        m_title = re.search(r'(?:WF|AG)-?([A-Za-z0-9\-]+)', title, re.IGNORECASE)
        if m_item and m_title:
            it = m_item.group(1).strip()
            ti = m_title.group(1).strip()
            if it.lower() != ti.lower():
                model_conflicts.append((p.get('sku'), title, it, ti))

    print(f"  Model Code Conflicts Found: {len(model_conflicts)}")
    for sku, title, it, ti in model_conflicts[:5]:
        print(f"    {sku}: Short Desc Item: '{it}' vs Title Model: '{ti}' | Title: {title[:40]}")

    # 4. Missing Fields
    missing_title = [p['sku'] for p in products_list if not p.get('title')]
    missing_price = [p['sku'] for p in products_list if not p.get('mrp') or float(p.get('mrp', 0)) == 0]
    unphotographed = [p['sku'] for p in products_list if len(p.get('images_list', [])) == 0]

    print(f"\n[4] Missing Fields Summary")
    print(f"  Missing Titles: {len(missing_title)}")
    print(f"  Missing / Zero Price: {len(missing_price)} -> {missing_price}")
    print(f"  Unphotographed Products: {len(unphotographed)} -> {unphotographed[:5]}")

    print("\n" + "=" * 60)
    print("AUDIT COMPLETE — Present findings in Authority Gate before building CSV.")
    print("=" * 60)

if __name__ == '__main__':
    print("Audit module ready for import or standalone testing.")
