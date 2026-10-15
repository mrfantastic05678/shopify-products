# Import formats

## Contents
- Column sets per operation
- Identifying rows in an export
- Body (HTML) formatting
- SEO field conventions
- Multi-tier tag and category architecture
- Inventory CSV (separate import)
- Matrixify notes
- Price arithmetic & compare-at conventions
- Multi-currency catalog rebuilding
- Public image hosting workflows

---

## Column sets per operation

Include only what you're changing, plus the identifiers. Every extra column is a chance to overwrite something.

**Price update**
```
Handle, Title, Option1 Name, Option1 Value, Variant SKU, Variant Price
```
`Title` is optional for updating an existing product but useful for human review of the file. Only include it if you're pulling the current value from the export.

**Content / SEO rewrite**
```
Handle, Title, Body (HTML), SEO Title, SEO Description
```

**Tag restructure**
```
Handle, Title, Tags
```
Tags are replace-not-merge. Emit the complete final tag string, not just the new tags.

**Combined content + price** (only when the user asks for one file)
```
Handle, Title, Body (HTML), Option1 Name, Option1 Value,
Variant SKU, Variant Price, SEO Title, SEO Description
```
Every cell filled from the current export where the operation doesn't change it. See the column rule in SKILL.md.

**New product upload with images**
```
Handle, Title, Body (HTML), Vendor, Product Category, Type, Tags, Published,
Option1 Name, Option1 Value, Variant SKU, Variant Grams,
Variant Inventory Tracker, Variant Inventory Policy, Variant Fulfillment Service,
Variant Price, Variant Compare At Price, Variant Requires Shipping, Variant Taxable,
Image Src, Image Position, Image Alt Text, SEO Title, SEO Description, Status
```
New products are the one case where image rows are correct: first row carries everything, subsequent rows carry `Handle` + `Image Src` + `Image Position` + `Image Alt Text` only.

---

## Identifying rows in an export

A Shopify export interleaves three row types under the same handle:

| Row type | How to spot it |
|---|---|
| Product + first variant | `Title` populated |
| Additional variant | `Variant Price` populated, `Title` blank |
| Image only | `Variant Price` blank, `Image Position` populated |

Practical filters:

```python
variants = df[df['Variant Price'].notna()]                 # all real variants
products = df[df['Title'].notna()].drop_duplicates('Handle')  # one row per product
```

`Option1 Name` appears **only on the first row of each product** in an export. When building an import file, backfill it onto every variant row of that handle — take it from the product's first row so it stays internally consistent (`Title`, `Size`, `Packaging`, whatever that product uses).

Single-variant products use `Option1 Name = Title` and `Option1 Value = Default Title`.

---

## Body (HTML)

The field is raw HTML. Plain text from a client sheet should be wrapped:

```python
body = '<p>' + text.strip() + '</p>'
```

Multi-paragraph text: split on blank lines and wrap each, or use `<br>` if matching an existing product's style. Check what the store already uses before choosing — consistency inside a store matters more than which convention is objectively better.

---

## SEO fields

`SEO Title` and `SEO Description` map to the page title and meta description in the Shopify admin.

Stores usually have a house format. Look at existing values in the export before inventing one:

```python
df['SEO Title'].dropna().head(20)
```

A common pattern is `<Product Name> - <Store Name>`. When a client sheet supplies bare names and the store uses a suffix, flag the discrepancy and ask rather than silently picking one. When the sheet has no SEO title at all, the product's new name is the sensible default.

For missing meta descriptions, derive from the supplied body copy in the same shape the sheet uses for its other rows — typically `<Name> with <two or three features>, <use case>.` Keep them roughly 120–160 characters.

---

## Product Category (Standardized Taxonomy) vs Type (Custom)

Shopify enforces a strict division between standard taxonomy categories and custom types:

| Field | CSV Column | Allowed Values | Usage / Purpose |
|---|---|---|---|
| **Product Category** | `Product Category` | Exact canonical path from [Shopify Standard Product Taxonomy](https://help.shopify.com/manual/products/details/product-type#product-category-and-product-types) | Automated sales tax, Google/Facebook channel syncing, and native Shopify filtering. Invalid strings trigger: *"Your import contains an invalid product category"*. |
| **Product Type** | `Type` | Any custom string (e.g. `Air Fryer`, `Baby Care`, `Hair Serum`) | Custom collection rules, internal merchant organization, and custom theme storefront navigation. |

### Taxonomy Resources & Category List
- **Documentation:** [Shopify Help Center: Product Category and Product Types](https://help.shopify.com/manual/products/details/product-type#product-category-and-product-types)
- **Interactive Explorer:** [Shopify Standard Product Taxonomy Explorer](https://shopify.github.io/product-taxonomy/)
- **Complete Canonical List:** [Shopify Product Taxonomy Releases (GitHub)](https://github.com/Shopify/product-taxonomy/releases/latest) — download `categories.en.txt.gz` for all 14,000+ official paths.

---

## Multi-tier tag and category architecture

Shopify automated collections and navigation filters depend on clean tags. Structure tags across 4 hierarchical tiers:

1. **Master Category:** Primary department tag (e.g. `Jewellery`, `Toys & Games`, `Phone Accessories`).
2. **Sub-Category:** Functional collection tag (e.g. `Earrings`, `Headphones & Earbuds`, `RC Toys`).
3. **Child / Specific Category:** Targeted style or format (e.g. `Jhumka`, `Wireless Earbuds`, `Die-Cast Models`).
4. **Attributes & Features:** Facet tags for sidebar filtering (e.g. `Gold Plated`, `Bluetooth`, `Type-C`, `Fast Charging`, `Educational`).

Format as clean, comma-separated tokens:
```python
clean_tags = []
seen = set()
for t in tags:
    ct = t.strip()
    if ct and ct.lower() not in seen:
        seen.add(ct.lower())
        clean_tags.append(ct)
final_tag_str = ", ".join(clean_tags)
```

---

## Inventory is a separate import

The products CSV has **no quantity column**. Stock is a second import:

- Products → Admin → Products → Import
- Inventory → Admin → Products → Inventory → Import

Import products first; inventory rows won't match otherwise.

Inventory CSV columns:
```
Handle, Title, Option1 Name, Option1 Value, Option2 Name, Option2 Value,
Option3 Name, Option3 Value, SKU, HS Code, COO, Location, Bin name,
Incoming (not editable), Unavailable (not editable), Committed (not editable),
Available (not editable), On hand (current), On hand (new)
```

**One row per variant per location.** A store with two locations produces two rows per variant. Quantity goes in `On hand (new)`.

- **Fulfillment / Stocked Location:** Set `On hand (new)` to target quantity. Set `Available (not editable)` to target quantity, `On hand (current)` to 0. If unstated in source sheet, use fallback (e.g. `6`).
- **Unstocked Location:** Set `On hand (new)` to empty string `""`. Set all non-editable columns to the literal string `not stocked`.

Always derive the location names from a real inventory export rather than typing them — they can contain unexpected spacing (e.g. double spaces between store name and branch) that must match exactly.

---

## Matrixify

Matrixify accepts the native Shopify column names plus its own extensions, so files built for the standard importer generally work. Two operational notes:

- Large collection or catalog files are worth splitting into parts (a few hundred rows each) so a failure costs one part, not the whole run
- Matrixify's `Command` column (`UPDATE`, `REPLACE`, `MERGE`) controls overwrite behaviour explicitly; when it's available, `MERGE` is safer than the native importer's implicit blank-clearing

---

## Price arithmetic & compare-at conventions

Store prices as strings formatted to two decimals: `'%.2f' % value`.

Percentage increases produce decimals the client rarely wants. Use explicit decimal quantization with `ROUND_HALF_UP` to prevent Banker's rounding bias:

```python
from decimal import Decimal, ROUND_HALF_UP

def calc_compare_at_price(price, markup=0.30):
    p = float(price)
    cap = int(Decimal(str(p * (1 + markup))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return f"{cap:.2f}"
```

After any bulk arithmetic, verify the ratio across all changed rows:

```python
set((new / old).round(6))    # should be a single expected ratio, e.g. {1.3}
```

Compare-at prices are a separate column and don't move automatically. If the store shows strikethrough pricing, raising `Variant Price` without touching `Variant Compare At Price` can produce a "discount" that's now higher than the original. Verify `Variant Compare At Price` exceeds `Variant Price` on all promotional rows.

---

## Catalog Rebuilding and Converted Pricing (Multi-Currency Reference)

When building a new store or market catalogue from scratch using an existing store's JSON API cache (`products.json`), apply these structural operations:
1. **Deduplicate handles:** Re-categorize all products into standard collections and filter out duplicate entries.
2. **Currency Conversion:** Convert catalog prices from local currency to target currency (e.g. USD) by pulling base pricing from the cache, applying the current exchange rate, and rounding cleanly to 2 decimal places:
   ```python
   def convert_price(local_str, rate=1/278.0):
       try:
           val = float(local_str)
           if val <= 0: return ""
           return f"{round(val * rate, 2):.2f}"
       except:
           return ""
   ```
3. **Tags Cleanup:** Clean tag lists to prevent character-level string iteration (which results in invalid tag structures like `M, e, n, ,`). Verify whether tags are stored as strings or lists, split appropriately, and discard single-letter tags before writing to the CSV.

---

## Public Hosting of Local Images

Shopify bulk product imports require images to be hosted on public web URLs (local files like `d:\images\image.jpg` will fail to import). To use local images in a bulk CSV upload, choose one of two workflows:

### Method 1 — Public Direct File Host (Anonymous API Workflow)
1. **Upload anonymously to a public direct host:** Use a python script to POST files as multipart/form-data to a public, permanent hosting API:
   ```python
   boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
   parts = [
       f"--{boundary}",
       'Content-Disposition: form-data; name="reqtype"',
       '',
       'fileupload',
       f"--{boundary}",
       f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"',
       f'Content-Type: image/jpeg',
       '',
   ]
   ```
2. **Implement persistent URL caching:** Save the mapping from local filename to public URL in a JSON file (`uploaded_images_urls.json`) to prevent duplicating uploads upon running the script again.
3. **Map and distribute in CSV:** Write a connector script to match the uploaded URLs to product variant handles, writing the primary URL to the main row (`Image position = 1`) and secondary views to variant image rows (`Image position = 2`).

### Method 2 — Public Git Repository Raw URLs (Exact Filename Preservation Workflow)
Use this method when you require the actual image filename in Shopify's CDN / Files to retain the exact descriptive product title (since Shopify extracts media filenames directly from the URL path, whereas anonymous hosts use random hash IDs):

1. **Clean & Rename Files:** Normalize and rename images to clean product names (e.g. `{clean_product_name}_{index}.png`) into a dedicated directory like `public_images/`.
   - **Thumbnail Selection Rule:** Assign the primary hero image (e.g., `02` image, `02_thumb`, or main product shot) as `_1.png` (`Image Position = 1`).
   - Additional product angles follow as `_2.png`, `_3.png` (`Image Position = 2, 3...`).
2. **Push to a Public Git Repository:**
   ```bash
   git init
   git add public_images
   git commit -m "Add product images"
   git branch -M main
   git remote add origin https://github.com/<username>/<repo-name>.git
   git push -u origin main
   ```
3. **Construct Raw URLs:** Format the URLs using raw content endpoints:
   ```text
   https://raw.githubusercontent.com/<username>/<repo-name>/main/public_images/<filename.png>
   ```
4. **Pre-flight Verify URLs:** Concurrently ping all URLs via HTTP GET/HEAD requests to verify `HTTP 200 OK` before generating the final CSV.
5. **Populate CSV:** Assign primary image to `Image Position = 1` and additional views to position 2+ rows. Set `Status = active` & `Published = true` for photographed items, and `Status = draft` & `Published = false` for unphotographed items.

---

## Single Master Consolidated Import CSV Standards

When importing multiple product batches (e.g., Electronics + Gardening), avoid generating fragmented CSVs. Consolidate into a single master CSV:

### Standard Columns (27 Headers)
```text
Handle, Title, Body (HTML), Vendor, Product Category, Type, Tags, Published,
Option1 Name, Option1 Value, Variant SKU, Variant Grams,
Variant Inventory Tracker, Variant Inventory Policy, Variant Fulfillment Service,
Variant Price, Variant Compare At Price, Variant Requires Shipping, Variant Taxable,
Variant Barcode, Image Src, Image Position, Image Alt Text, Gift Card,
SEO Title, SEO Description, Status
```

### Essential Integrity Rules:
1. **100% Unique Handles:** Every product MUST have a distinct handle. For duplicate listings placed in Draft, append `-category-slug` to the handle to prevent variant collapse in Shopify.
2. **Explicit Store Status on First Row:** Set `Status = active` & `Published = true` for approved items; set `Status = draft` & `Published = false` for items needing client review.
3. **Multi-Image Formatting:** First row carries all metadata and hero thumbnail (`Image Position = 1`). Subsequent rows carry `Handle`, `Image Src`, `Image Position = 2, 3...`, and `Image Alt Text` ONLY.
4. **Smart Tag Hardening:** Include both singular and plural forms of key categories (`Insect Killer`, `Insect Killers`, `Electric Insect Killer`) so existing and new Shopify Smart Collections match immediately.

---

## Client Review & Audit Workbook Schema (6-Tab Standard)

Always generate a companion multi-tab `.xlsx` workbook for the client, keeping all sheet tab titles $\le 31$ characters:

1. **`Executive Summary`**: High-level KPI summary cards (Total SKUs, Active count, Draft count, Markup percentages, Total images staged, and explicit Client Action Items).
2. **`Duplicate Listings`**: Side-by-side comparison of duplicate SKUs, primary vs secondary categories, primary vs secondary MRPs, price differences, binary photo uniqueness, and draft recommendations.
3. **`Data & Image Issues`**: Resolution log of mislabeled image prefixes (e.g. 137A vs 136A), title copy-paste collisions, and missing image files.
4. **`Gaps & Unpriced Items`**: Products omitted from factory sheets (e.g. SKU 207) or items lacking photos, held in draft with benchmark pricing.
5. **`Model Code Variances`**: Comparison of factory short description item codes vs e-commerce title model numbers (e.g. 81 vs WF-81B).
6. **`Full Catalog (N Products)`**: Complete catalog inventory with SKUs, Product Titles, Categories, Selling Prices, Compare-At Prices, Markup %, Weights, Inventory quantities, and store status (`ACTIVE` vs `DRAFT`).

