# Authority & Questions Gate Template (Pre-Execution Decision Protocol)

Use this template to present catalog audit findings and request explicit user decisions **before** writing import CSVs, altering product statuses, or pushing changes.

---

## 1. Executive Summary & Verification Stats

| Metric | Batch A (e.g., Electronics) | Batch B (e.g., Non-Electronics) | Total / Store Scope |
| :--- | :--- | :--- | :--- |
| **Source Workbook / Sheet** | `[Filename.xlsx]` (`Sheet`) | `[Filename.xlsx]` (`Sheet`) | Total source rows |
| **Total Products Identified** | N products | N products | Total unique SKUs |
| **Total Images Staged / Found**| N images across N folders | N images on disk | Total image files |
| **Selling Price Source** | Column `MRP` / `Selling Price` | Column `MRP` | Base retail cost |
| **Compare-At Price (CAP)** | **+20%** (range 18–22%) | **+30%** (range 28–30%) | Standardized e-commerce CAP |
| **Stock Inventory Rule** | Column `QTY` (fallback: 6) | Column `QTY` (fallback: 6) | Total inventory units |

---

## 2. Inconsistencies & Anomaly Findings

### A. Duplicate Listings & Category Collisions
- **Finding:** [List products appearing across multiple categories with different MRPs or SKUs].
- **Binary Image Analysis:** [State whether image files are byte-for-byte identical copies via MD5 hash or if separate photos exist].
- **Proposed Default:** Publish the primary instance as `Status = active`; place duplicate instances in `Status = draft` with disambiguated handles (`handle-category-name`).

### B. Missing Data, Skipped Rows & Ghost SKUs
- **Finding:** [List SKUs skipped in working sheets or listed in raw sheets without pricing, descriptions, or image folders].
- **Proposed Default:** Place skipped SKUs with photos in `Status = draft` with benchmark pricing; completely exclude ghost SKUs that lack image assets.

### C. Model Code & Title Contradictions
- **Finding:** [List items where raw factory description item codes diverge from e-commerce title models (e.g. 81 vs WF-81B)].
- **Proposed Default:** Retain title model codes as they are unique and e-commerce facing.

### D. Smart Collection Tags (Singular vs Plural)
- **Finding:** [Check existing collections in the store (e.g. `Insect Killers` vs `Insect Killer`)].
- **Proposed Default:** Enrich tags with both singular and plural forms (`Insect Killer`, `Insect Killers`, `Electric Insect Killer`) so products populate all collection filters automatically.

---

## 3. Explicit Authority Questions (User Decision Required)

Please provide your confirmation on the following before import files are generated:

1. **Duplicate Listings Decision:**
   - [ ] **Option A (Recommended):** Set secondary duplicate listings to `Status = draft` and document price differences in the client review sheet.
   - [ ] **Option B:** Publish all instances as `Status = active` with category suffixes in their titles.

2. **Unpriced / Skipped SKUs:**
   - [ ] **Option A (Recommended):** Include in import sheet as `Status = draft` with benchmark pricing pending client confirmation.
   - [ ] **Option B:** Completely exclude until client provides official pricing.

3. **Collection & Tag Strategy:**
   - [ ] **Option A (Recommended):** Enrich tags with both singular and plural variants to ensure compatibility with existing store collections.
   - [ ] **Option B:** Strict single-tag matching.

4. **File Delivery Structure:**
   - [ ] **Option A (Recommended):** Single consolidated master import CSV containing all batches with embedded active/draft statuses.
   - [ ] **Option B:** Separate fragmented CSVs per category.
