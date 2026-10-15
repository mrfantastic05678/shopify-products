---
name: shopify-catalog-ops
description: Build and validate Shopify product-import CSVs from messy client or supplier spreadsheets — price updates, compare-at calculations, title/description/SEO rewrites, multi-tier tag architectures, public image hosting via Git/CDN, bulk uploads, and multi-location inventory files. Use this skill whenever a Shopify products export, a supplier catalog, or an inventory sheet is involved, and whenever the user mentions Shopify import errors, Matrixify, product handles, variants, SKUs, or bulk catalog edits — even if they only ask to "update a sheet" without saying Shopify. It encodes the import rules and failure modes that cause silent data loss, so consult it before writing any matching or CSV-building code.
---

# Shopify Catalog Operations

Bulk Shopify edits fail in two ways: **loudly** (the import rejects rows and you can see it) or **silently** (the import succeeds and quietly wipes descriptions, resets SEO, or reprices the wrong product). Loud failures cost an afternoon. Silent ones cost trust with the client, because nobody notices for a week.

This skill exists to keep both from happening. The core discipline: **inspect the real data before writing any logic, match on identifiers rather than resemblance, use deterministic arithmetic, and never guess when you can report.**

---

## The Workflow

1. **Inspect** every input file — shape, column headers, how variants, options, and images are laid out.
2. **Match** the source rows to existing products using the strict matching hierarchy, and verify disk image assets.
3. **Audit & Report** all discrepancies, model variances, duplicate rows, missing prices, and image anomalies.
4. **The Authority & Questions Gate (MANDATORY)**: Present the plan and discrepancy findings to the user. Ask clarifying questions and obtain explicit user authority before writing import files, assigning draft statuses, or pushing changes. Never guess client pricing or unilaterally decide duplicate status.
5. **Build** the appropriate import file:
   - *For new multi-batch uploads:* Single consolidated master import CSV containing all batches with 100% unique handles, explicit `Status` (`active` vs `draft`), and primary/supplementary image rows.
   - *For existing catalog edits:* Delta-only import file, exactly one row per variant, no image rows.
   - *For stock updates:* Separate inventory CSV matching store locations.
6. **Validate** against the pre-flight checklist with automated validation scripts and HTTP CDN pings.
7. **Deliver** the single ready-to-import master CSV, unified inventory CSV, and a companion multi-tab review Excel workbook.

Do not skip step 1 or step 4. Supplier spreadsheets frequently have shifted columns, merged header rows, inconsistent formatting, and duplicate listings with conflicting prices. A wrong assumption at the start propagates through the entire catalog.

---

## Step 1 — Inspect Before You Write Logic

Load all data with `dtype=str` always. Pandas will turn a SKU like `0012` into `12`, a price into a float with rounding anomalies, and a barcode into scientific notation.

```python
import pandas as pd

export_df = pd.read_csv(export_file, dtype=str)                   # Existing Shopify export
supplier_p = pd.read_excel(supplier_sheet, dtype=str, header=None) # Raw client/supplier sheet
```

For the Shopify export, establish these numbers before writing code:

```python
len(export_df)                            # Total rows (including image rows)
export_df['Handle'].nunique()             # Actual unique product count
export_df['Variant Price'].notna().sum()  # Actual variant count
```

Rows greatly exceed handles because **image rows** pad every product. A row is a variant if `Variant Price` or `Option1 Value` is populated; otherwise it is an image row.

Check supplier sheets for these common anomalies:
- **Header not in row 1.** Inspect rows 0 to 5 to find where column names actually reside and use `header=N`.
- **Shifted columns.** A column inserted partway down shifts every field to the right for those rows only. Detect programmatically (e.g. if a `Description` cell equals `Title`).
- **Trailing or interleaved blank rows.** Always apply `dropna(how='all')` and `dropna(subset=[key_column])`.
- **Inconsistent units & formatting.** Normalize units (e.g. `5L` → `5000ml`, `1KG` → `1000g`) before matching.
- **Identifier & Model Code Contradictions (Copy-Paste Drift).** When a sheet contains both raw supplier/technical names (`Product Name`, `Item No`, `Model`) and drafted store fields (`Product Title`, `SEO Title`), writers often introduce off-by-one row shifts, formula drag errors, or cross-category copy-paste mistakes (e.g. pasting an oven title onto a garment steamer row, or shifting model codes by 1 row across an entire section). Cross-compare model numbers across columns programmatically and report all discrepancies during the inspection step before creating import files.

---

## Step 2 — The Matching Hierarchy

Match in this order and stop at the first tier that resolves cleanly:

1. **Variant SKU / Item Code** — Normalize both sides with `re.sub(r'[^a-z0-9]', '', s.lower())` to absorb spacing and case differences. Verify the SKU maps to exactly one product.
2. **Handle** — Exact slug match after identical normalization.
3. **Exact Normalized Title** — Reliable when the source sheet originated from a store export.
4. **Explicit Hand-Written Mapping** — A dictionary keyed by `(item_name, pack_size/attribute)` pointing to an unambiguous SKU/Handle.

> [!WARNING]
> **Do not auto-apply fuzzy matching.** Fuzzy scoring is a triage tool for building explicit candidate lists, not a decision procedure. Subtle model variations score above 95% against each other and will silently assign pricing or specs to the wrong item. Use fuzzy matching only to generate a list for human review.

---

## Step 3 — Report, Don't Guess

Anything that does not resolve cleanly to exactly one variant must go into a review file, never into an import file:

| Category | Definition | Action |
|---|---|---|
| **Not found** | Product does not exist on the store | Skip and list in review sheet |
| **Ambiguous** | Multiple candidates match; source does not disambiguate | Flag for client decision |
| **Duplicate SKU** | One SKU assigned to multiple products | Flag data anomaly |
| **Cross-Category Duplicate Listings** | Identical product listed under multiple categories with different MRPs | Inspect binary image hashes; primary published, secondary drafted pending client decision |
| **Model / Title Conflict** | Model code in `Product Name` contradicts model in `Product Title` | Flag discrepancy immediately to user before generating CSV |
| **Title Copy-Paste Collision** | Different products given identical titles (e.g. Zinnia Mixed vs Zinnia Linearis) | Disambiguate title to preserve unique Shopify URL handles |
| **Mislabeled Image Prefix** | Disk images named with adjacent row number (e.g. 137A instead of 136A) | Resolve via title keyword mapping; flag in review sheet |
| **Binary Image Duplication** | Duplicate rows reuse exact byte-for-byte identical photo files | Draft secondary listing; flag to client |
| **Unphotographed** | Product is listed in sheet but has no image files | Default to `Status = draft`, `Published = false` |
| **Unlisted Image** | Images exist on disk but have no row in the pricing sheet | Report in review sheet |
| **Unpriced / Skipped SKU** | SKU skipped in working sheet (e.g. 206 -> 208) but image exists | Create as `Status = draft` with benchmark price; flag for client price |
| **Already correct** | Target values already match store values | Exclude to keep delta small |

---

## Step 3B — The Authority & Questions Gate (MANDATORY)

Never proceed directly from catalog inspection into file generation or git pushes without user authorization. When inconsistencies, pricing conflicts, or duplicate items are detected:

1. **Stop at the Plan Phase:** Present an Executive Summary and Discrepancy Audit artifact to the user first.
2. **Formulate Explicit Questions:** Ask clear, structured questions outlining the exact tradeoffs:
   - *Duplicate Listings:* "Products X and Y appear across two categories with different MRPs. Are there separate photos? Should we disambiguate titles and publish both, or set secondary listings to Draft?"
   - *Missing Prices / Skipped Rows:* "SKU N has images on disk but is unpriced in the working sheet. Should we draft it with benchmark pricing or exclude it?"
   - *Model Variances:* "16 items have model suffixes in titles (WF-81B) that differ from factory item numbers (81). Should we preserve the title model codes?"
   - *Tag & Smart Collection Strategy:* "The store already has an 'Insect Killer' collection. Should we enrich tags with both singular and plural variants, and should chemical insecticides share this collection or remain separate?"
3. **Wait for Explicit Authority:** Implement only what the user confirms. Default all unresolved exceptions to `Status = draft`, `Published = false`.

---

## Step 4 — Building Import Files

Read `references/import-formats.md` for exact column sets per operation.

### Operation A: Delta Updates (Price, Tags, SEO, Content)
- **One row per variant.** Deduplicate strictly on `(Handle, Option1 Value)`.
- **No image rows.** Never include image rows in a price or content update file; Shopify will interpret them as duplicate variants with blank prices.
- **Delta only.** Include only products that have changes.
- **First row carries product metadata.** For multi-variant products, `Title`, `Body (HTML)`, `SEO Title`, `SEO Description`, `Tags`, and `Vendor` belong on the first row only; subsequent variant rows carry `Handle` plus variant attributes.

### Operation B: New Catalog Uploads with Images
- **First row:** Contains complete product metadata (`Title`, `Body (HTML)`, `Vendor`, `Type`, `Tags`, `Status`, `Published`, option fields, `Variant SKU`, pricing, and primary image).
- **Primary Image (Thumbnail):** Assign the designated hero image (e.g., `02`, `02_thumb`, or main product shot) to `Image Position = 1` on the first row.
- **Supplementary Image Rows:** Subsequent rows under the same handle carry `Handle`, `Image Src`, `Image Position` (`2, 3, 4...`), and `Image Alt Text`. All other columns must remain empty.
- **Unphotographed Items:** Set `Status = draft` and `Published = false` so empty placeholders never appear live on the storefront.

### Operation C: Multi-Tier Tag Architecture for Automated Collections
Shopify collections are populated dynamically using tag conditions (`Product tag is equal to <TAG>`). Structure product tags across four distinct tiers:

1. **Master Category:** Broad collection level (e.g., `Phone Accessories`, `Toys & Games`, `Jewellery`).
2. **Sub-Category:** Functional group (e.g., `Headphones & Earbuds`, `Chargers & Adapters`, `Die-Cast Models`).
3. **Child Category / Style:** Specific form factor (e.g., `Wireless Earbuds`, `Fast Chargers`, `RC Toys`).
4. **Product Attributes & Features:** Filter facets (e.g., `Bluetooth`, `Type-C`, `Rechargeable`, `Lights & Sound`).

> [!CAUTION]
> **The String-Splitting Tag Bug:** Always verify whether tags are stored as strings or lists. Iterating over a comma-separated string `for t in tags:` iterates character-by-character and creates single-letter tags (`T`, `o`, `y`, `s`), which corrupts the catalog. Always parse with:
> ```python
> tags_list = [t.strip() for t in tags.split(',') if t.strip()] if isinstance(tags, str) else tags
> ```

### Operation D: Public Image Hosting via Git Repository
When client images reside on local disks, Shopify bulk imports require publicly accessible URLs. Use the Git Raw URL workflow for permanent hosting with clean filenames:

1. **Organize & Rename:** Normalize image names to descriptive product titles: `{clean_title}_{index}.{ext}`. Avoid raw supplier codes in URLs if clean SEO names are preferred.
2. **Commit & Push:** Add images to `public_images/` in a public repository and push to GitHub.
3. **Construct Raw URLs:**
   ```text
   https://raw.githubusercontent.com/<owner>/<repo>/<branch>/public_images/<filename>
   ```
4. **Automated Pre-Flight URL Verification:** Concurrently ping 100% of raw image URLs via HTTP GET/HEAD requests to confirm `HTTP 200 OK` before generating the final CSV.

### Operation E: Multi-Location Inventory Import
The product CSV does not control stock levels. Stock quantity is imported separately via **Products → Inventory → Import**.

- **Exact Location Matching:** Derive location names directly from an official store inventory export. Beware of subtle whitespace or double spaces (e.g. `Main Store  - Central Warehouse`).
- **One row per variant per location:**
  - *Fulfillment / Stocked Location:* `On hand (new) = <quantity>`, `Available (not editable) = <quantity>`, `On hand (current) = 0`. If quantity is unstated in source sheets, use the designated store fallback (e.g., `6`).
  - *Secondary / Unstocked Location:* `On hand (new) = ""` (blank), and all non-editable status columns set to the literal string `not stocked`.

### Operation F: Compare-At Price (CAP) Arithmetic
When calculating promotional strike-through pricing (e.g., +30% or +32% markup), avoid Python's standard `round()`, which uses banker's rounding (rounding half to even) and causes margin drift:

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_compare_at(selling_price, markup_pct=0.30):
    p = float(selling_price)
    cap = int(Decimal(str(p * (1 + markup_pct))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return f"{cap:.2f}"
```

Verify that `Variant Compare At Price` is strictly greater than `Variant Price` on all promotional rows.

### Operation G: Single Master Consolidated Import CSV Standard
Merchants and store owners heavily prefer a **single consolidated import file** over juggling fragmented CSVs across multiple categories or draft statuses:
- **All batches unified in one file:** Combine all product lines (e.g. Westpoint Electronics, MTS Gardening) into a single master import CSV (e.g. `WinBachat_Products_Shopify_Import.csv`).
- **Handle Uniqueness Guarantee:** Ensure every single product has a strictly unique handle across the entire consolidated file. If duplicates exist in draft, append category suffixes to the handle (e.g. `-plants-insecticide-fungicide`) so Shopify creates distinct products rather than collapsing them into unintended variants.
- **Embedded Store Status:** Include `Status` (`active` vs `draft`) and `Published` (`true` vs `false`) explicitly on the first row of each product so approved products go live immediately while flagged duplicates sit safely in draft.

### Operation H: Smart Collection Tag Hardening (Singular vs Plural)
Shopify Automated (Smart) Collections evaluate exact string conditions (`Product tag is equal to <TAG>`). Slight naming differences break collection population silently:
- **Singular vs Plural Tag Trap:** If an existing collection searches for `Insect Killers` (plural), products tagged with `Insect Killer` (singular) will not show up.
- **Hardening Rule:** Always emit both singular and plural variants, plus functional descriptors (e.g., attach both `Insect Killer` AND `Insect Killers`, `Electric Insect Killer`, `Insecticides`, and `Pest Control`). This guarantees 100% compatibility across existing and newly created smart collection filters without manual tagging in the admin.

### Operation I: Excel 31-Character Tab Name Limit in Review Workbooks
When generating formatted `.xlsx` client review workbooks using `openpyxl`, sheet tab names cannot exceed 31 characters:
- Exceeding 31 characters raises `UserWarning: Title is more than 31 characters` and triggers Excel repair warnings when opened by the client.
- Always truncate or design concise tab names:
  ```python
  ws.title = title[:31]  # E.g. 'MTS Duplicate Listings' instead of 'MTS Duplicates & Price Conflicts'
### Operation J: Standard Product Taxonomy & Product Category Compliance
Shopify strictly separates **Product Category** (Shopify's Standard Product Taxonomy) from **Type** (custom product types):

- **`Product Category` (The Standardized Taxonomy Column):** Must strictly match a predefined canonical path from Shopify's Standard Product Taxonomy (e.g. `Health & Beauty > Personal Care > Cosmetics > Perfumes & Colognes` or `Home & Garden > Kitchen & Dining > Kitchen Appliances`).
  - **The Warning:** If an unstandardized, custom, or typo-ridden string is entered into `Product Category`, Shopify imports the product but ignores the category, displaying:
    > *"Your import contains an invalid product category. You can still import but any invalid categories will not be set. See the Shopify Product Taxonomy for a list of valid product categories."*
  - **Official Documentation Reference:** [Shopify Help Center: Product Category and Product Types](https://help.shopify.com/manual/products/details/product-type#product-category-and-product-types)
  - **Official Taxonomy Lists & Downloads:**
    - Interactive Taxonomy Explorer: [Shopify Standard Product Taxonomy](https://shopify.github.io/product-taxonomy/)
    - Canonical Categories List: [Shopify Product Taxonomy Releases (GitHub)](https://github.com/Shopify/product-taxonomy/releases/latest) (download `categories.en.txt.gz` containing all 14,000+ valid hierarchical category paths).
- **`Type` (The Custom Store Category Column):** Use the `Type` column (formerly `custom-product-type`) for internal organization, supplier classifications, and custom collection rules (e.g. `Baby Lotion`, `Insect Killer`, `Air Fryer`).
- **Common Taxonomy Traps & Canonical Resolutions:**
  - *Trap:* `Baby & Toddler > Baby Care` (Invalid) $\rightarrow$ *Fix:* `Health & Beauty > Personal Care > Cosmetics > Skin Care` (for baby oils, powders, lotions) or `Baby & Toddler > Baby Health`.
  - *Trap:* `Health & Beauty > Personal Care > Fragrances` (Invalid) $\rightarrow$ *Fix:* `Health & Beauty > Personal Care > Cosmetics > Perfumes & Colognes`.
  - *Trap:* `Health & Beauty > Personal Care > Skin Care` (Invalid) $\rightarrow$ *Fix:* `Health & Beauty > Personal Care > Cosmetics > Skin Care`.
  - *Formatting Rule:* Always maintain exact spacing and casing around greater-than symbols: `Parent > Child > Grandchild`.

---

## Step 5 — Pre-Flight Validation

Always execute the automated validator before delivering any CSV to the user:

```bash
python scripts/validate_import.py <import_file.csv>
```

The validator verifies:
- **Handle Integrity:** No missing or blank handles.
- **Handle Uniqueness:** Exactly one defining product row per unique handle.
- **Product Category Taxonomy Compliance:** 100% of non-empty values in `Product Category` strictly exist in Shopify's Standard Product Taxonomy, preventing category import warnings.
- **Option Uniqueness:** No duplicate `(Handle, Option1 Value)` pairs across variant rows.
- **Price Completeness:** No blank `Variant Price` on rows carrying an option value.
- **Option Names & Values:** Properly populated variant columns without gaps.
- **Product Headers:** First row of each handle carries title, status, and product fields.
- **Image Rows:** Properly isolated for new uploads; absent for delta updates.
- **Publish Safety:** Explicit `Status` (`active` or `draft`) and `Published` (`true` or `false`) on product-defining rows.

---

## Step 6 — Delivery Standard

Deliver three distinct assets for every catalog operation:

1. **Single Master Products Import CSV (`Admin > Products > Import`):**
   - Consolidated master CSV containing all products, handles, pricing, tags, and staged GitHub CDN image URLs.
2. **Unified Inventory Import CSV (`Admin > Products > Inventory > Import`):**
   - Matching all unique handles and SKUs with exact store location names and stock quantities.
3. **Client-Facing Multi-Tab Review Workbook (`.xlsx`):**
   - **Tab 1: Executive Summary:** KPI cards, total product counts (active vs draft), markup rules, and client action items.
   - **Tab 2: Duplicate Listings & Price Conflicts:** Side-by-side comparison of duplicate SKUs, contrasting categories, price differences, and draft recommendations.
   - **Tab 3: Data & Image Issues:** Log of image folder/prefix typos, copy-paste title clashes, and resolutions.
   - **Tab 4: Gaps & Unpriced Items:** Skipped rows or items missing factory pricing/descriptions held in draft.
   - **Tab 5: Model Code Variances:** Side-by-side comparison of factory technical item numbers vs title model numbers.
   - **Tab 6: Full Catalog Review:** Complete catalog of all items with selling prices, compare-at prices, weights, categories, inventory, and active/draft status.

---

## Reference Files & Templates

### Documentation References
- `references/import-formats.md` — Complete column sets per operation type, single master import standards, 6-tab review workbook schema, inventory schema, Git/CDN image hosting workflows, and pricing formulas.
- `references/pitfalls.md` — Error messages playbook, silent-failure prevention, tag traps, location spacing traps, taxonomy standards, and real-world multi-batch traps.

### Templates
- `templates/audit_questions_template.md` — Mandatory Authority & Questions Gate template for presenting findings and securing user confirmation before file generation.
- `templates/shopify_product_import_template.csv` — Standard 27-column Shopify product import template demonstrating active, draft, and multi-image rows.
- `templates/shopify_inventory_import_template.csv` — Standard 19-column Shopify inventory import template matching store locations.

### Operational Scripts
- `scripts/audit_catalog_discrepancies.py` — Automated discrepancy scanner (cross-category duplicates, binary MD5 image checks, missing fields, model code variances).
- `scripts/build_master_import.py` — Single consolidated master Shopify CSV builder with unique handles, Decimal ROUND_HALF_UP CAP, and smart tag hardening.
- `scripts/generate_client_review_workbook.py` — Generates formatted 6-tab `.xlsx` client review workbook enforcing 31-character tab limits.
- `scripts/validate_import.py` — Pre-flight validator for product imports.
- `scripts/inspect_export.py` — One-shot structural summary of a Shopify export.
- `scripts/verify_image_urls.py` — Concurrently verifies that public image URLs return HTTP 200 before catalog import.

