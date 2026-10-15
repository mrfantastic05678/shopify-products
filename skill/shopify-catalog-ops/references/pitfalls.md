# Pitfalls

## Contents
- Part 1: Import error messages → causes → fixes
- Part 2: Silent failures (import succeeds, outcome is wrong)
- Part 3: Source data traps
- Part 4: Colour variant + metaobject workflow (Swatch Setup Reference)
- Part 5: Shopify 2.0 Tag and Category Pitfalls (Taxonomy & Tag Format Reference)
- Part 6: Multi-Image and Inventory Traps

---

# Part 1 — Import error messages

Shopify reports failures as line ranges, e.g. `Line 2-4: Validation failed: ...`. The range is the row group belonging to one handle. A range of 3 lines for a single-variant product means two extra rows were included — almost always image rows.

### `The variant 'Default Title' already exists`

Two or more rows under the same handle carry `Option1 Value = Default Title`.

Cause, nearly always: image rows were left in the file. In an export, image rows sit under the same handle and repeat the option value with no price.

Fix: filter to `df['Variant Price'].notna()`, then deduplicate on `(Handle, Option1 Value)`.

Same error for multi-variant products means a genuinely repeated option value — check whether the source sheet lists the same size twice.

### `Price can't be blank`

A row has an option value but no `Variant Price`. Image rows again, or a source row where the price cell was empty.

Fix: drop image rows; drop or flag source rows with no price rather than emitting a blank.

These two errors appear together constantly, because one image row triggers both.

### `Handle can't be blank`

Trailing blank rows survived to the output. `dropna(subset=['Handle'])` before writing.

### `Option1 Name can't be blank` / options mismatch

`Option1 Name` was taken from a variant row where the export left it blank. Backfill from the product's first row.

### Rows import but the product doesn't change

The handle doesn't exist in the store. Shopify creates a new product instead of updating. Verify every handle in the import file exists in the export before delivering — a typo or a handle from a stale export creates duplicates silently.

### `Your import contains an invalid product category`

**The Warning:** Shopify displays: *"Your import contains an invalid product category. You can still import but any invalid categories will not be set. See the Shopify Product Taxonomy for a list of valid product categories."*

**Cause:** The string in the `Product Category` column does not match Shopify's official Standard Product Taxonomy hierarchy verbatim. Common triggers include:
1. Using an intuitive custom category instead of standard taxonomy (e.g. `Baby & Toddler > Baby Care` or `Health & Beauty > Personal Care > Fragrances`).
2. Skipping parent levels (e.g. writing `Health & Beauty > Personal Care > Skin Care` instead of `Health & Beauty > Personal Care > Cosmetics > Skin Care`).
3. Spacing or formatting mistakes around the `>` delimiter.

**Fix:**
- Consult the official guide: [Shopify Product Category and Product Types](https://help.shopify.com/manual/products/details/product-type#product-category-and-product-types).
- Search the taxonomy tree at [Shopify Standard Product Taxonomy Explorer](https://shopify.github.io/product-taxonomy/) or match against the canonical `categories.en.txt` download from [Shopify Product Taxonomy Releases](https://github.com/Shopify/product-taxonomy/releases/latest).
- Map custom labels (like `Baby Care` or `Air Fryer`) into the `Type` column, leaving `Product Category` strictly populated with canonical taxonomy strings.

---

# Part 2 — Silent failures

These are worse than errors. The import reports success and something is wrong anyway.

### Market price overrides beat Variant Price

Stores with Shopify Markets can have per-market price columns, e.g. `Price / Pakistan`, `Compare At Price / Pakistan`, `Included / Pakistan`. When a market price is set for a product, **it is what shoppers in that market see**, and updating `Variant Price` changes nothing for them.

Always check:

```python
overrides = df[df['Price / Pakistan'].notna()]['Handle']
affected = set(overrides) & set(import_file['Handle'])
```

Report `affected` to the user. Either the market column needs updating too, or the override needs removing in the admin. This is invisible in the import result and can go unnoticed for weeks.

Column names vary per store — scan for any column matching `Price / ` before assuming there are none.

### Blank cells clearing fields

Restating the central rule because it is the most expensive mistake available:

- Column **not present** → field unchanged
- Column present, cell **blank** → field may be cleared

Descriptions, SEO fields, tags, and vendor are all vulnerable. Before adding a column to an import file, ask whether every row has a real value for it. If not, either fill from the current export or drop the column.

### Tags replace rather than merge

Emitting `Tags` at all replaces the entire tag string. Adding one tag means writing out all existing tags plus the new one. Read current tags from the export, append, re-emit.

### Duplicate SKUs across products

Shopify does not enforce SKU uniqueness. A SKU-based match returning two products means a real data problem in the store. Never pick one — report both handles and let the user decide. Silently repricing the wrong one is undetectable from the import result.

### Partial variant imports are fine, partial products are not

Including only some variants of a multi-variant product is safe — Shopify leaves the others alone. But including a handle with product-level columns and blank values *will* touch those product-level fields. Variant-level partial: safe. Product-level partial: dangerous.

### Status and Published

`Status` (`active` / `draft` / `archived`) and `Published` (`true` / `false`) are separate. Including either column with a blank or wrong value can unpublish a live product. Leave both out unless changing them deliberately.

---

# Part 3 — Source data traps

### Shifted columns mid-sheet

A column inserted partway down a client sheet shifts every field after it, for those rows only. The header row still describes the original layout, so `pandas` labels are wrong for the shifted section.

Detect structurally rather than by eyeballing. If two columns hold identical values on a row where they shouldn't, that's the tell:

```python
shifted = (row['DESCRIPTION'] == row['NAME UPDATE'])
body = row['PAGE TITLE'] if shifted else row['DESCRIPTION']
```

Handle it per row. Mixed layouts within one sheet are common.

### Model number & Title mismatches (Copy-paste drift & Off-by-one shifts)

When a spreadsheet contains both technical supplier columns (`Product Name`, `Item No`, `Model`) and e-commerce copy columns (`Product Title`, `Description`, `SEO Title`), writers frequently introduce **copy-paste drift** and **off-by-one row shifts**:

1. **Off-by-one model shifts:** A copywriter drafts titles while glancing at adjacent rows, causing model codes to shift by 1 row down an entire series (e.g. Row $N$ lists `Item No : 3086` but the title is written as `Model 3088`, which is actually Row $N+1$).
2. **Cross-category copy-paste:** A template block is pasted into the wrong section (e.g. a small appliance title/description like `Oven Toaster` pasted onto a garment steamer row, or `Electric Kettle` pasted onto a food blender row).
3. **Generic titles omitting model numbers:** Writers write identical generic titles (e.g. `Electric Stand Mixer with Stainless Steel Bowl`) across distinct models, losing the specific model number that customers search for and triggering duplicate handle errors in Shopify.

**Detection & Mitigation Rule:**
Always extract technical model numbers from both the supplier name/code column and the drafted title column using regex before generating import files. Cross-compare and report every contradiction to the user during the initial audit phase:

```python
# Check for model code divergence
p_model = re.search(r'Item\s*No\s*[:\.]?\s*(\w+)', pname)
t_model = re.search(r'(?:AG[- ]?|Model\s*[:\.]?\s*)(\w+)', title)
if p_model and t_model and p_model.group(1).lower() != t_model.group(1).lower():
    # Flag conflict immediately before generating import files
    report_discrepancy(row, p_model.group(1), t_model.group(1))
```

### Two schemas in one sheet

Supplier sheets often have a coded section (item codes matching store SKUs) and an uncoded section (supplier's internal product names). The uncoded section is the hard one and usually needs an explicit hand-written mapping. Split them and handle separately; don't try one matcher for both.

### Sizes expressed inconsistently

`5LTR`, `5 Ltr`, `5000ml`, `5L` are the same. Normalize to a base unit before comparing:

```python
if unit in ('l','ltr','litre','liter'): n *= 1000; unit = 'ml'
if unit == 'kg': n *= 1000; unit = 'gm'
if unit in ('g','gram','gms'): unit = 'gm'
```

### Supplier names that don't match store names

The same product is often named differently by the supplier and in the store. There's no rule that recovers this — it needs a human-verified mapping. Build it once as an explicit dict, keyed on `(item_name, pack_size)`, so it's reviewable and reusable next time the supplier sends a sheet.

### Sizes or variants the store doesn't carry

Supplier lists are catalogues, not store inventory. Expect a meaningful fraction to have no listing. Skip and report — don't force them onto the nearest match.

### Values that need no change

Some matched rows already carry the target value. Excluding them keeps the import small and makes the diff meaningful. List them separately so the user knows they were seen, not missed.

---

# Part 4: Colour variant + metaobject workflow (Swatch Setup Reference)

This section documents the full end-to-end process for adding colour swatches to existing Shopify products that already have variants. It covers multi-shade products like lipsticks, glosses, nail polishes, and beauty items.

## How colour swatches work in Shopify

Shopify's native colour picker requires three things to be in place simultaneously:

1. **Metaobject entries** — each shade must exist as a `shopify--color-pattern` entry in Content → Metaobjects, with a `label` (name), `color` (hex), `image`, `color_taxonomy_reference`, and `pattern_taxonomy_reference` field.
2. **Product metafield** — the product's `Color (product.metafields.shopify.color-pattern)` field must list the entry handles semicolon-separated.
3. **Option linked** — `Option1 Linked To = product.metafields.shopify.color-pattern` must be set on the product.

All three must exist before the swatch picker renders. Missing any one of them produces either blank swatches, text buttons, or the "Edit N option values to finish connecting" error.

## Step-by-step process

### Step 1 — Identify entry handles

Entry handles are the slugified option values from the store. Slugify with:
```python
re.sub(r'[^a-z0-9]+', '-', str(val).lower().strip()).strip('-')
```
So option value `Peach Glazed 01` → handle `peach-glazed-01`, `102` → `102`, `Nailpolish451` → `nailpolish451`.

### Step 2 — Export existing metaobject entries via Matrixify

Matrixify → Export → Metaobjects → filter by Definition: Name = Color (or Color pattern). This gives you the exact column names and existing handles so you don't duplicate.

The export format is **one row per field per entry** (5 rows per entry):

| Handle | Command | Definition: Handle | Field | Value |
|---|---|---|---|---|
| 102 | MERGE | shopify--color-pattern | label | 102 |
| 102 | | | color | #613626 |
| 102 | | | image | |
| 102 | | | color_taxonomy_reference | gid://shopify/TaxonomyValue/7 |
| 102 | | | pattern_taxonomy_reference | gid://shopify/TaxonomyValue/2874 |

`pattern_taxonomy_reference` is always `gid://shopify/TaxonomyValue/2874` (solid pattern). `color_taxonomy_reference` varies by hue family — use `gid://shopify/TaxonomyValue/7` (red) as default for cosmetics.

### Step 3 — Import metaobject entries via Matrixify (free tier: 10 per import)

- Use `Command = NEW` to avoid touching existing entries
- Split into batches of 10 entries (50 rows) per CSV
- Errors showing "Handle already exists" on some rows = those entries were already created — not a real error, safe to ignore
- File name must contain the word "metaobjects" for Matrixify to detect the entity type

### Step 4 — Link the option in admin (manual, one click per product)

Once all metaobject entries exist:
- Admin → Products → [product] → Variants → click the option name (e.g. "Shade")
- A **Color** button appears top-right → click it → Done → Save
- The "Edit N option values" error only appears when entries are missing — it disappears once Step 3 is complete

### Step 5 — Products import to set Option1 Linked To

After linking in admin, also import via native Shopify importer to persist `Option1 Linked To` in the CSV record:

```
Handle, Title, Option1 Name, Option1 Value, Option1 Linked To, Variant SKU, Variant Price
```

**Critical:** keep `Option1 Name` exactly as it exists in the store. Renaming it (e.g. from `Shade` to `Color`) causes `Invalid CSV value` errors for every option value — Shopify treats it as a new option structure and rejects all existing values.

### Step 6 — Variant images (separate import or Matrixify)

Variant images cannot be imported via native Shopify importer when images are hosted on the store's own CDN — the importer returns `File original source missing`. Use Matrixify for variant image imports. See Part 1 for the full error playbook.

## Key pitfalls specific to colour variant setup

- **Metaobjects free tier is 10 per import** — split large shade sets into 10-entry batches, name files with "metaobjects" in the filename, import one by one. Matrixify resets the counter per import so each batch uses its own 10-slot allocation.
- **Option1 Name rename breaks imports** — always read `Option1 Name` from the current export before writing the import file. Never assume it is `Color` or `Shade`.
- **Color metafield value format** — the `Color (product.metafields.shopify.color-pattern)` column stores slugified entry handles semicolon-separated, not hex codes. Writing raw hex codes here has no effect.
- **Taxonomy references are required** — omitting `color_taxonomy_reference` or `pattern_taxonomy_reference` from metaobject entries causes `Missing required Metaobject field(s)` errors even though entries are created. Both fields must be present in every import row.
- **Product category must be set** — colour metafields only appear on products assigned to a valid Shopify taxonomy category. Products set to `Uncategorized` will not show the Color metafield at all. Set categories first via a separate products import before attempting colour linking.

---

# Part 5 — Shopify 2.0 Tag and Category Pitfalls (Taxonomy & Tag Format Reference)

This section documents specific validation failures and spelling warnings encountered during multi-market catalog setups.

### The String-Splitting Tag Trap
When extracting or enriching tags from cached or fetched API data, the `tags` field might be returned as a raw comma-separated string (e.g. `"Men, Perfume"`) instead of an array of strings. 
Iterating directly over a string in Python:
```python
# BUG: If tags is a string, this iterates character-by-character!
existing_tags = [t.strip() for t in tags if isinstance(t, str)]
```
Creates individual single-letter tags (e.g. `M`, `e`, `n`, `,`, `P`, `e`, etc.). This causes Shopify imports to fail with:
`Validation failed: Product tags is invalid`

**Fix:** Detect if the tags field is a string and split it by comma before compiling, filtering out empty tags or single-character tags:
```python
if isinstance(tags, str):
    existing_tags = [t.strip() for t in tags.split(',') if t.strip()]
elif isinstance(tags, list):
    existing_tags = [t.strip() for t in tags if isinstance(t, str) and t.strip()]
else:
    existing_tags = []
```

### Strict Standard Category Taxonomy
Shopify utilizes a strict Standard Product Category taxonomy. Misspelled paths, incorrect casing, plural forms, or missing hyphens will fail validation. Shopify will successfully import the products but will throw warnings and leave the category blank.

Example:
* **Invalid (warned):** `Health & Beauty > Personal Care > Deodorants & Antiperspirants`
* **Valid:** `Health & Beauty > Personal Care > Deodorants & Anti-Perspirant` (singular and hyphenated).

**Fix:** Always check your taxonomy categories against the official Shopify Taxonomy Explorer or standard taxonomy lists before generating the CSV.

---

# Part 6 — Multi-Image and Inventory Traps

### The Image Row Duplicate Option Trap
When uploading multiple images for a single-variant product, the first row carries `Option1 Name = Title` and `Option1 Value = Default Title`. 
If secondary image rows also carry `Option1 Value = Default Title` without a `Variant Price`, Shopify rejects the import with:
`The variant 'Default Title' already exists` and `Price can't be blank`.

**Fix:** On secondary image rows (Image Position 2+), leave all option and pricing columns completely blank. Only populate `Handle`, `Image Src`, `Image Position`, and `Image Alt Text`.

### The Location Spacing Trap
Shopify inventory locations are matched by literal string comparison. If a store's location has unintentional whitespace (such as a double space between the store name and branch name, e.g. `Main Store  - Central Branch`), typing it with a single space (`Main Store - Central Branch`) causes Shopify to reject the row or create a shadow unlinked inventory line.

**Fix:** Never manually type location strings. Extract them directly from a fresh `inventory_export.csv` exported from the target Shopify admin.

### The Unphotographed Ghost Product Trap
Importing products that do not have photos as `Status = active` and `Published = true` causes them to immediately render as broken image icons or blank grey boxes on collection pages.

**Fix:** Set `Status = draft` and `Published = false` for any item lacking image assets, and surface them in a dedicated "Pending Photos" tab of your review workbook.

### Banker's Rounding Margin Drift
Standard Python `round(x)` implements round-half-to-even (Banker's Rounding), where `round(2.5) == 2` and `round(3.5) == 4`. When computing compare-at price markups across a catalog, this silently produces inconsistent markups where some products get rounded down instead of up.

**Fix:** Use Python's `decimal` module with `ROUND_HALF_UP`:
```python
from decimal import Decimal, ROUND_HALF_UP
clean_cap = int(Decimal(str(price * (1 + markup))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
```

---

# Part 7 — Real-World Catalog Traps & Learnings (Multi-Batch & Store Ops)

### 1. The Authority Bypass Trap (Never Guess Before Asking)
**Problem:** The assistant rushes into generating import files or pushing commits before presenting discrepancy findings to the user. When supplier spreadsheets contain duplicate SKUs, missing prices, or conflicting categories, making unilateral assumptions ruins catalog integrity.
**Rule:**
- Always execute the **Inspection & Plan Phase first**.
- Present an exhaustive discrepancy audit artifact detailing all gaps, model variances, and duplicate listings.
- Formulate specific, multiple-choice questions to get explicit user authority before writing files or assigning store statuses.

### 2. The Cross-Category Duplicate & Price Clash Trap
**Problem:** A supplier sheet lists the exact same product twice under different categories with wildly divergent prices (e.g. `One Shot DDVP 100ml` at Rs. 554.62 in *Roaches Control* vs Rs. 3,451.00 in *General Insects*; `Plant Safe & Care 250ml` at Rs. 1,109.25 vs Rs. 554.62).
**Consequences:** If imported blindly, Shopify either collapses them into variants, overwrites prices, or creates duplicate listings that confuse shoppers and trigger supplier price losses.
**Fix:**
- Group products by normalized title and identify all cross-category duplicates.
- Compare image assets using MD5 hashes to see if separate photos exist.
- Keep the primary product `Status = active` (`Published = true`).
- Set secondary duplicate listings to `Status = draft` (`Published = false`) with disambiguated handles (e.g. appending `-category-name`).
- Document all price differences side-by-side in a dedicated "Duplicates & Price Conflicts" review tab for the client.

### 3. The Binary Image Duplicate Trap
**Problem:** When a product is listed twice in a spreadsheet, image folders may contain duplicate copies of the same image under different filenames/prefixes (e.g. `22A-Plant Safe...` in Fertilizers and `51A-Plant Safe...` in Insecticides).
**Fix:** Check binary hashes (`hashlib.md5`) and file sizes. If images are byte-for-byte identical, there are no distinct photoshoot angles; draft the duplicate product unless the user explicitly commands separate publication.

### 4. The Mislabeled Image Prefix Trap
**Problem:** Photographers or spreadsheet preparers often mislabel image file prefixes on disk by 1 row (e.g. Gaillardia Seeds row 136A has files named `137A-Gaillardia Seeds...` on disk, while Zinnia Mixed row 137A also has files starting with `137A`).
**Fix:** Never rely purely on numeric prefix matching. Always implement a secondary title/keyword matching fallback to rescue mislabeled assets before declaring an image missing.

### 5. The Title Copy-Paste Handle Collision Trap
**Problem:** Copywriters paste identical titles across distinct products (e.g. pasting `Zinnia Linearis Mixed Seeds Pack of 3` onto the `Zinnia Mixed Seeds` row).
**Consequences:** Shopify slugifies titles into handles. Identical titles generate identical handles, causing Shopify to reject the row or treat the second product as a variant of the first, corrupting option combinations.
**Fix:** Programmatically detect identical titles across distinct SKUs. Disambiguate the title (e.g. `Zinnia Mixed Seeds Pack of 3 – Multi-Color Flower Seeds`) before computing handles, ensuring 100% unique handles across the catalog.

### 6. The Singular vs. Plural Smart Collection Tag Trap
**Problem:** Existing store collections use exact match conditions (`Product tag is equal to Insect Killers` [plural]). If a new batch is imported with `Insect Killer` [singular], products fail to show up in the collection silently.
**Fix:**
- Always inspect existing catalog tags before choosing tag nomenclature.
- Hardening pattern: Emit both singular and plural forms, plus functional descriptors (e.g., tag with both `Insect Killer` AND `Insect Killers`, `Electric Insect Killer`, `Insecticides`, and `Pest Control`).
- Products will automatically populate existing collections regardless of whether the store owner configured singular or plural filter rules.

### 7. The Excel 31-Character Sheet Title Limit Trap
**Problem:** In `openpyxl`, setting `ws.title` longer than 31 characters raises a warning: `UserWarning: Title is more than 31 characters. Some applications may not be able to read the file`. When opened in Microsoft Excel, it prompts the user with a repair error dialog.
**Fix:** Always enforce `ws.title = title[:31]`. Keep sheet names concise (e.g. `'MTS Duplicate Listings'` instead of `'MTS Duplicates & Price Conflicts'`).

### 8. The Fragmented Import Sheet Fatigue
**Problem:** Delivering separate CSVs for each supplier batch (e.g. `Westpoint.csv`, `Gardening.csv`, `Draft_Update.csv`) creates confusion and manual work for store managers.
**Fix:** Always consolidate into **one single master import CSV** (`WinBachat_Products_Shopify_Import.csv`) with:
- All product batches unified.
- 100% unique handles guaranteed.
- Explicit `Status` (`active` vs `draft`) set on every row.
- Accompany with one unified inventory CSV and one comprehensive multi-tab review Excel workbook.

