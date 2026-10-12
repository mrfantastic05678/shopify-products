#!/usr/bin/env python3
"""Pre-flight validator for Shopify product import CSVs.

Usage:
    python validate_import.py <import.csv> [--export <shopify_export.csv>]

Checks the structural rules that cause rejected imports or silent data loss.
Passing --export additionally verifies every handle already exists in the store
(a missing handle means Shopify creates a duplicate product instead of updating).

Exit code 0 = clean, 1 = problems found.
"""
import sys
import argparse
import pandas as pd


def check(df, export=None):
    errors, warnings, info = [], [], []
    cols = set(df.columns)

    info.append(f"{len(df)} rows, {df['Handle'].nunique()} handles"
                if 'Handle' in cols else f"{len(df)} rows")

    # --- Handle ---
    if 'Handle' not in cols:
        errors.append("No 'Handle' column — Shopify cannot match rows to products.")
        return errors, warnings, info

    blank_handle = df['Handle'].isna() | (df['Handle'].astype(str).str.strip() == '')
    if blank_handle.any():
        errors.append(f"{blank_handle.sum()} row(s) with a blank Handle "
                      f"(rows {list(df.index[blank_handle][:5] + 2)}). "
                      "Usually trailing blank rows — drop them.")

    # --- Image rows must not be present ---
    img_cols = [c for c in ('Image Src', 'Image Position', 'Image Alt Text') if c in cols]
    if img_cols:
        warnings.append(
            f"Image column(s) present: {', '.join(img_cols)}. "
            "Safe only for new-product uploads. For updates, image rows cause "
            "\"variant 'Default Title' already exists\" and \"Price can't be blank\".")

    # --- Duplicate variants ---
    if 'Option1 Value' in cols:
        # If this is a new product upload with image rows, only check variant rows (where Option1 Value is non-blank or Variant Price is present)
        variant_df = df[df['Variant Price'].notna() | df['Option1 Value'].notna()] if img_cols else df
        dup = variant_df.duplicated(['Handle', 'Option1 Value'], keep=False)
        if dup.any():
            pairs = (variant_df.loc[dup, ['Handle', 'Option1 Value']]
                     .fillna('<blank>').drop_duplicates().head(5).values.tolist())
            sample = '; '.join(f"{h} / {v}" for h, v in pairs)
            errors.append(f"{dup.sum()} row(s) share a (Handle, Option1 Value) pair — "
                          f"this triggers \"variant already exists\". "
                          f"A blank option value here usually means image rows survived. "
                          f"Examples: {sample}")

    # --- Variant rows need a price ---
    if 'Variant Price' in cols and 'Option1 Value' in cols:
        has_opt = df['Option1 Value'].notna() & (df['Option1 Value'].astype(str).str.strip() != '')
        no_price = df['Variant Price'].isna() | (df['Variant Price'].astype(str).str.strip() == '')
        bad = has_opt & no_price
        if bad.any():
            errors.append(f"{bad.sum()} row(s) carry an option value but no Variant Price — "
                          "this triggers \"Price can't be blank\".")

    # --- Option columns populated on variant rows ---
    if 'Variant Price' in cols:
        variant_rows = df['Variant Price'].notna() & (df['Variant Price'].astype(str).str.strip() != '')
        for c in ('Option1 Name', 'Option1 Value'):
            if c in cols:
                blank = variant_rows & (df[c].isna() | (df[c].astype(str).str.strip() == ''))
                if blank.any():
                    errors.append(f"{blank.sum()} variant row(s) with a blank {c}. "
                                  "Backfill from the product's first row in the export.")

    # --- First row of each handle carries the product fields ---
    if 'Title' in cols:
        missing = [h for h, g in df.groupby('Handle', sort=False)
                   if str(g.iloc[0].get('Title', '') or '').strip() == '']
        if missing:
            errors.append(f"{len(missing)} handle(s) whose first row has a blank Title. "
                          f"Examples: {missing[:5]}")

    # --- Blank cells in product-level columns (silent clearing risk) ---
    for c in ('Body (HTML)', 'SEO Title', 'SEO Description', 'Tags', 'Vendor'):
        if c in cols:
            firsts = df.groupby('Handle', sort=False).head(1)
            blank = firsts[c].isna() | (firsts[c].astype(str).str.strip() == '')
            if blank.any():
                warnings.append(
                    f"'{c}' is present but blank on the first row of {blank.sum()} handle(s). "
                    "A blank cell in an included column can clear the field. "
                    "Fill from the current export or drop the column.")

    # --- Status / Published safety ---
    for c in ('Status', 'Published'):
        if c in cols:
            check_df = df.groupby('Handle', sort=False).head(1) if img_cols else df
            blank = check_df[c].isna() | (check_df[c].astype(str).str.strip() == '')
            if blank.any():
                errors.append(f"'{c}' present with {blank.sum()} blank cell(s). "
                              "This can unpublish live products. Fill it or drop the column.")

    # --- Handles must already exist ---
    if export is not None:
        known = set(export['Handle'].dropna())
        unknown = sorted(set(df['Handle'].dropna()) - known)
        if unknown:
            errors.append(f"{len(unknown)} handle(s) not found in the export — Shopify will "
                          f"CREATE new products rather than update. Examples: {unknown[:5]}")
        else:
            info.append("All handles exist in the export.")

        # market price override warning
        mkt = [c for c in export.columns if c.startswith('Price / ')]
        for mc in mkt:
            ov = set(export.loc[export[mc].notna(), 'Handle'])
            hit = ov & set(df['Handle'])
            if hit:
                warnings.append(
                    f"{len(hit)} product(s) in this file have a '{mc}' override set. "
                    "That market price is what shoppers see — updating Variant Price "
                    "will not change it.")

    return errors, warnings, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--export', help='Shopify products export, for handle + market checks')
    a = ap.parse_args()

    df = pd.read_csv(a.csv, dtype=str)
    export = pd.read_csv(a.export, dtype=str, low_memory=False) if a.export else None

    errors, warnings, info = check(df, export)

    for i in info:
        print(f"  ·  {i}")
    print()
    for w in warnings:
        print(f"  WARN   {w}\n")
    for e in errors:
        print(f"  ERROR  {e}\n")

    if errors:
        print(f"FAILED — {len(errors)} error(s), {len(warnings)} warning(s). Fix before importing.")
        sys.exit(1)
    print(f"PASSED — 0 errors, {len(warnings)} warning(s).")
    sys.exit(0)


if __name__ == '__main__':
    main()
