#!/usr/bin/env python3
"""One-shot structural summary of a Shopify products export.

Usage:
    python inspect_export.py <shopify_export.csv> [--sku SKU] [--handle HANDLE]

Run this first, before writing any matching logic. It answers the questions
that shape every downstream decision: how many real products, how many
variants, which option schemes are in use, whether market price overrides
exist, and whether any SKU is shared by more than one product.
"""
import argparse
import re
import pandas as pd


def norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--sku', help='look up a specific SKU')
    ap.add_argument('--handle', help='dump all rows for a handle')
    a = ap.parse_args()

    df = pd.read_csv(a.csv, dtype=str, low_memory=False)

    variants = df[df['Variant Price'].notna()]
    products = df[df['Title'].notna()].drop_duplicates('Handle')

    print(f"rows            {len(df)}")
    print(f"products        {df['Handle'].nunique()}")
    print(f"variants        {len(variants)}")
    print(f"image rows      {len(df) - len(variants)}")
    print(f"columns         {len(df.columns)}")

    multi = variants.groupby('Handle').size()
    print(f"multi-variant   {(multi > 1).sum()} products "
          f"(max {multi.max()} variants)")

    print("\noption schemes in use:")
    for name, n in products['Option1 Name'].value_counts(dropna=False).head(10).items():
        print(f"  {str(name):<20} {n}")

    print("\nstatus / published:")
    for c in ('Status', 'Published'):
        if c in df.columns:
            print(f"  {c}: {df[c].value_counts(dropna=False).to_dict()}")

    mkt = [c for c in df.columns if c.startswith('Price / ') or c.startswith('Included / ')]
    if mkt:
        print("\nmarket columns (these can override Variant Price):")
        for c in mkt:
            print(f"  {c:<32} {df[c].notna().sum()} populated")

    sk = variants[variants['Variant SKU'].notna()].copy()
    sk['n'] = sk['Variant SKU'].map(norm)
    dups = sk.groupby('n')['Handle'].nunique()
    dups = dups[dups > 1]
    if len(dups):
        print(f"\nSKUs on more than one product: {len(dups)}")
        for n in list(dups.index)[:10]:
            hs = sk.loc[sk['n'] == n, ['Variant SKU', 'Handle']]
            print(f"  {hs.iloc[0]['Variant SKU']:<24} -> {list(hs['Handle'])}")
    else:
        print("\nSKUs unique across products: yes")

    missing_sku = variants['Variant SKU'].isna().sum()
    if missing_sku:
        print(f"\nvariants with no SKU: {missing_sku} (match these by handle)")

    if a.sku:
        n = norm(a.sku)
        hit = sk[sk['n'] == n]
        print(f"\nSKU {a.sku!r}: {len(hit)} match(es)")
        if len(hit):
            print(hit[['Handle', 'Option1 Value', 'Variant Price']].to_string(index=False))

    if a.handle:
        rows = df[df['Handle'] == a.handle]
        print(f"\nhandle {a.handle!r}: {len(rows)} row(s)")
        show = [c for c in ('Title', 'Option1 Name', 'Option1 Value', 'Variant SKU',
                            'Variant Price', 'Image Position', 'SEO Title')
                if c in rows.columns]
        print(rows[show].to_string(index=False))


if __name__ == '__main__':
    main()
