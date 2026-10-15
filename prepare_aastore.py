import os
import re
import csv
import shutil
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Paths
SOURCE_WORKBOOK = r"WinBachat/AA Dot Store Products.xlsx"
SOURCE_IMAGE_DIR = r"WinBachat/AA Dot Store Cosmetics Date 06-10-2026"
PUBLIC_IMAGES_DIR = r"public_images/winbachat"
GITHUB_IMG_BASE = "https://raw.githubusercontent.com/mrfantastic05678/shopify-products/main/public_images/winbachat/"

AA_SHOPIFY_CSV = "WinBachat_AA_Dot_Store_Shopify_Import.csv"
AA_INVENTORY_CSV = "WinBachat_AA_Dot_Store_Inventory_Import.csv"
AA_REVIEW_XLSX = "WinBachat_AA_Dot_Store_Review_and_Audit.xlsx"
CONSOLIDATED_MASTER_CSV = "WinBachat_Products_Shopify_Import.csv"

SHOPIFY_HEADERS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type",
    "Tags", "Published", "Option1 Name", "Option1 Value", "Variant SKU",
    "Variant Grams", "Variant Inventory Tracker", "Variant Inventory Policy",
    "Variant Fulfillment Service", "Variant Price", "Variant Compare At Price",
    "Variant Requires Shipping", "Variant Taxable", "Variant Barcode",
    "Image Src", "Image Position", "Image Alt Text", "Gift Card",
    "SEO Title", "SEO Description", "Status"
]

def clean_text(text):
    if not text:
        return ""
    text = str(text)
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2015', '-')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\ufffd', '-')
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def slugify(text):
    text = clean_text(text).lower()
    text = re.sub(r'[\'\"]', '', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def clean_filename(name):
    base, ext = os.path.splitext(name)
    clean_base = re.sub(r'[^a-zA-Z0-9]+', '_', base).strip('_')
    return f"{clean_base}{ext.lower()}"

def stage_images():
    os.makedirs(PUBLIC_IMAGES_DIR, exist_ok=True)
    art_to_images = {}
    
    for root, dirs, files in os.walk(SOURCE_IMAGE_DIR):
        folder_name = os.path.basename(root).strip()
        if not folder_name.startswith("A Art"):
            continue
        art_code = folder_name
        art_slug = re.sub(r'[^a-zA-Z0-9]+', '_', art_code)
        
        art_to_images[art_code] = []
        for f in sorted(files):
            if not f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.avif')):
                continue
            src_path = os.path.join(root, f)
            dest_name = f"MRT-WB-AASTORE_{art_slug}_{clean_filename(f)}"
            dest_path = os.path.join(PUBLIC_IMAGES_DIR, dest_name)
            
            shutil.copy2(src_path, dest_path)
            art_to_images[art_code].append({
                "original_name": f,
                "dest_name": dest_name,
                "url": f"{GITHUB_IMG_BASE}{dest_name}"
            })
            
    print(f"Staged {sum(len(v) for v in art_to_images.values())} images across {len(art_to_images)} ART folders.")
    return art_to_images

def parse_weight_grams(weight_str, s_no, art):
    if not weight_str:
        return 100
    w_str = str(weight_str).strip().lower()
    
    # Handle A Art 23 compound weight
    if "0.055" in w_str and "0.110" in w_str:
        if s_no == 41:  # 200ml
            return 110
        elif s_no == 42:  # 100ml
            return 55
        return 110
        
    m = re.search(r'([\d\.]+)\s*(kg|g|gm)?', w_str)
    if m:
        val = float(m.group(1))
        unit = m.group(2) or 'kg'
        if unit == 'kg':
            return int(round(val * 1000))
        return int(round(val))
    return 100

def get_product_category(cat, sub_cat, product_name=""):
    c = (cat or "").strip().lower()
    s = (sub_cat or "").strip().lower()
    p = (product_name or "").strip().lower()
    
    # 1. Perfumes, Colognes, Body Sprays, Fragrances (including Baby Cologne)
    if "perfume" in c or "perfume" in s or "cologne" in s or "cologne" in p or "spray" in s or "scent" in s or "spray" in p:
        return "Health & Beauty > Personal Care > Cosmetics > Perfumes & Colognes"
    # 2. Hair Care (Hair treatments, masks, waxes, creams)
    elif "hair" in c or "hair" in s or "wax" in s or "hair" in p:
        return "Health & Beauty > Personal Care > Hair Care"
    # 3. Skin Care & Baby Skin Care (Lotions, Baby Oil, Baby Powder, Baby Jelly, Sheet Masks, Wipes, Sponges)
    elif "skin" in c or "mask" in s or "lotion" in s or "wipe" in s or "oil" in s or "powder" in s or "jelly" in s or "baby" in c or "baby" in s or "lotion" in p or "oil" in p or "powder" in p or "jelly" in p or "sponge" in p:
        return "Health & Beauty > Personal Care > Cosmetics > Skin Care"
    # 4. General Cosmetics & Makeup (Lip Balm, Lip Gloss, Makeup Blenders)
    else:
        return "Health & Beauty > Personal Care > Cosmetics"

def get_product_type(cat, sub_cat):
    s = (sub_cat or "").strip()
    if s:
        return s
    c = (cat or "").strip()
    if c:
        return c
    return "Cosmetics"

def main():
    print("Loading workbook...")
    wb = openpyxl.load_workbook(SOURCE_WORKBOOK, data_only=True)
    ws = wb['Working']
    
    art_images = stage_images()
    
    raw_rows = []
    art_parent_meta = {}
    
    for r_idx in range(2, ws.max_row + 1):
        row_vals = [ws.cell(row=r_idx, column=c).value for c in range(1, 15)]
        if not any(row_vals):
            continue
        s_no = int(row_vals[0])
        code = clean_text(row_vals[1] or '')
        art = clean_text(row_vals[2] or '')
        name = clean_text(row_vals[3] or '')
        cat_main = clean_text(row_vals[4] or '')
        cat = clean_text(row_vals[5] or '')
        sub_cat = clean_text(row_vals[6] or '') if row_vals[6] is not None else ""
        qty = int(row_vals[7]) if row_vals[7] is not None else 6
        mrp = float(row_vals[8]) if row_vals[8] is not None else 0.0
        weight_raw = row_vals[9]
        title_raw = clean_text(row_vals[10] or '') if row_vals[10] is not None else ""
        desc_raw = clean_text(row_vals[11] or '') if row_vals[11] is not None else ""
        seo_t_raw = clean_text(row_vals[12] or '') if row_vals[12] is not None else ""
        seo_d_raw = clean_text(row_vals[13] or '') if row_vals[13] is not None else ""
        
        row_obj = {
            "s_no": s_no,
            "raw_code": code,
            "art": art,
            "product_name": name,
            "cat_main": cat_main,
            "cat": cat,
            "sub_cat": sub_cat,
            "qty": qty,
            "mrp": mrp,
            "weight_raw": weight_raw,
            "title_raw": title_raw,
            "desc_raw": desc_raw,
            "seo_t_raw": seo_t_raw,
            "seo_d_raw": seo_d_raw
        }
        raw_rows.append(row_obj)
        
        if title_raw and art not in art_parent_meta:
            art_parent_meta[art] = {
                "base_title": title_raw,
                "base_desc": desc_raw,
                "base_seo_t": seo_t_raw,
                "base_seo_d": seo_d_raw,
                "base_weight": weight_raw,
                "base_sub_cat": sub_cat
            }
            
    print(f"Loaded {len(raw_rows)} rows. ART parent groups found: {len(art_parent_meta)}")
    
    products = []
    used_handles = set()
    
    for item in raw_rows:
        s_no = item["s_no"]
        art = item["art"]
        pname = item["product_name"]
        mrp = item["mrp"]
        qty = item["qty"]
        sku = f"MRT-WB-AASTORE-{s_no:03d}"
        
        parent = art_parent_meta.get(art, {})
        base_title = parent.get("base_title", pname)
        base_desc = parent.get("base_desc", "")
        base_seo_t = parent.get("base_seo_t", "")
        base_seo_d = parent.get("base_seo_d", "")
        base_weight = item["weight_raw"] or parent.get("base_weight", "0.100 kg")
        
        # Calculate Compare-At Price (+30% CAP)
        cap_price = round(mrp * 1.30)
        price = mrp
        
        # Parse Weight in Grams
        weight_grams = parse_weight_grams(base_weight, s_no, art)
        
        # Sub-category imputation if blank
        sub_cat = item["sub_cat"]
        if not sub_cat:
            if art == "A Art 07":
                sub_cat = "Sponge Set"
            elif art == "A Art 11":
                sub_cat = "Lip Gloss"
            elif art == "A Art 18":
                sub_cat = "Baby Cologne"
            elif art in ("A Art 24", "A Art 25"):
                sub_cat = "Baby Jelly"
            elif art == "A Art 27" or art == "A Art 28":
                sub_cat = "Perfumes"
            elif art == "A Art 30":
                sub_cat = "Body Spray"
            else:
                sub_cat = item["cat"]
                
        # Resolve Title, Description, and SEO Fields per product
        if art == "A Art 22":
            color_match = re.search(r'-\s*([a-zA-Z\s]+)$', pname)
            color_suffix = color_match.group(1).strip().capitalize() if color_match else "Pink"
            title = f"Liock Baby Lotion 100ml - {color_suffix}"
            desc = "<p>Give delicate skin gentle moisturizing care with Liock Baby Lotion 100ml. Formulated with mild, skin-nourishing ingredients to keep your baby's skin feeling soft, smooth, and comfortably hydrated throughout the day.</p>"
            seo_t = f"Liock Baby Lotion 100ml - {color_suffix}"
            seo_d = f"Shop Liock Baby Lotion 100ml ({color_suffix}) for gentle daily moisturizing. Helps soothe and protect delicate skin."
        elif art == "A Art 23":
            if s_no == 41:
                title = "Johnson's Baby Oil 200ml"
                desc = "<p>Give delicate skin gentle everyday care with Johnson's Baby Oil 200ml. Its clinically proven mild formula locks in up to 10 times more moisture on wet skin than ordinary lotion on dry skin. Perfect for soothing baby massage and keeping skin soft and smooth.</p>"
                seo_t = "Johnson's Baby Oil 200ml - Gentle Daily Moisturizer"
                seo_d = "Shop Johnson's Baby Oil 200ml for soothing baby massage and everyday moisturizing. Clinically proven mild for delicate skin."
            else:
                title = "Johnson's Baby Oil 100ml"
                desc = "<p>Give delicate skin gentle everyday care with Johnson's Baby Oil 100ml. Its clinically proven mild formula locks in up to 10 times more moisture on wet skin than ordinary lotion on dry skin. Perfect for travel, massage, and gentle baby skincare.</p>"
                seo_t = "Johnson's Baby Oil 100ml - Pure & Gentle Skin Care"
                seo_d = "Shop Johnson's Baby Oil 100ml for convenient travel moisturizing and delicate skincare. Pure, gentle, and nourishing."
        elif art == "A Art 24":
            title = "Nexton Baby Jelly 180ml"
            desc = "<p>Protect and soothe your baby's sensitive skin with Nexton Baby Jelly. Creates a gentle moisture barrier that helps prevent diaper rash, locks in natural hydration, and protects against dryness and chafing.</p>"
            seo_t = "Nexton Baby Jelly 180ml - Moisture Barrier & Rash Protection"
            seo_d = "Shop Nexton Baby Jelly 180ml for gentle skin protection and diaper rash prevention. Locks in moisture for baby soft skin."
        elif art == "A Art 25":
            color_suffix = "Blue" if "blue" in pname.lower() else "Pink"
            title = f"Johnson's Baby Jelly Fragrance Free 100ml - {color_suffix}"
            desc = "<p>Protect delicate skin from dryness and diaper rash with Johnson's Baby Jelly Fragrance Free 100ml. This lightly textured, gentle formula creates an effective protective barrier while locking in essential moisture.</p>"
            seo_t = f"Johnson's Baby Jelly Fragrance Free 100ml - {color_suffix}"
            seo_d = f"Shop Johnson's Baby Jelly Fragrance Free 100ml ({color_suffix}). Helps lock in moisture and protect delicate skin against chafing and irritation."
        elif art == "A Art 07":
            if s_no == 7:
                title = "Facial Cleansing Sponge - Soft & Gentle Beauty Tool"
            else:
                title = "Facial Cleansing Sponge - Soft & Gentle Beauty Sponge (Piece 2)"
            desc = base_desc if base_desc else f"<p>{title}. High quality skincare accessory for daily routine.</p>"
            seo_t = f"{title}"
            seo_d = base_seo_d if base_seo_d else f"Shop {title} online at Win Bachat."
        elif art == "A Art 08":
            flavor = "Blue (Hyaluronic Acid)" if "blue" in pname.lower() else ("Black (Caviar Nourishing)" if "black" in pname.lower() else "Orange (Vitamin C Radiance)")
            title = f"Assorted Facial Sheet Mask - {flavor}"
            desc = f"<p>Recharge your skincare routine with this refreshing facial sheet mask featuring {flavor}. Designed to deliver intense hydration and leave your face glowing, smooth, and revitalized.</p>"
            seo_t = f"Facial Sheet Mask - {flavor}"
            seo_d = f"Shop Assorted Facial Sheet Mask featuring {flavor}. Deep moisturizing and rejuvenating facial care."
        elif art == "A Art 10":
            shade = "Red" if "red" in pname.lower() else "Pink"
            title = f"Huda Moji Sweet Lip Strawberry Lip Gloss 4.5ml - {shade}"
            desc = f"<p>Treat your lips to juicy color and brilliant shine with Huda Moji Sweet Lip Strawberry Lip Gloss in {shade}. Infused with sweet strawberry essence to keep lips moisturized and irresistibly glossy.</p>"
            seo_t = f"Huda Moji Strawberry Lip Gloss 4.5ml - {shade}"
            seo_d = f"Shop Huda Moji Sweet Lip Strawberry Lip Gloss in {shade}. High shine moisturizing gloss with delicious strawberry scent."
        elif art == "A Art 11":
            shade = "Blue" if "blue" in pname.lower() else "Pink"
            title = f"Cute Cup Design Moisturizing Lip Gloss - {shade}"
            desc = f"<p>Add playful charm to your makeup bag with this Cute Cup Design Lip Gloss in {shade}. Delivers a soft hint of color and radiant shine while keeping lips hydrated and comfortable.</p>"
            seo_t = f"Cute Cup Design Lip Gloss - {shade}"
            seo_d = f"Shop Cute Cup Design Moisturizing Lip Gloss in {shade}. Fun cup-shaped container with smooth hydrating shine."
        elif art == "A Art 12":
            size_label = "Small" if "small" in pname.lower() else "Large"
            title = f"Enzo Fashion Hair Care Treatment - {size_label}"
            desc = f"<p>Restore softness and shine to dull or damaged hair with Enzo Fashion Hair Care Treatment ({size_label}). Enriched with conditioning agents to nourish strands from root to tip.</p>"
            seo_t = f"Enzo Fashion Hair Care Treatment - {size_label}"
            seo_d = f"Shop Enzo Fashion Hair Care Treatment ({size_label}) for deep conditioning and silky smooth hair."
        elif art == "A Art 13":
            color_suffix = "Pink" if "pink" in pname.lower() else ("Blue" if "blue" in pname.lower() else "Green")
            title = f"Wokali Salon Keratin Hair Mask with Vitamin E 500ml - {color_suffix}"
            desc = f"<p>Provide salon-quality nourishment at home with Wokali Salon Keratin Hair Mask ({color_suffix}) enriched with Vitamin E. Deeply repairs and strengthens hair fibres for soft, lustrous locks.</p>"
            seo_t = f"Wokali Salon Keratin Hair Mask 500ml - {color_suffix}"
            seo_d = f"Shop Wokali Salon Keratin Hair Mask with Vitamin E 500ml ({color_suffix}). Professional hair repair and smoothing treatment."
        elif art == "A Art 17":
            color_suffix = "Blue" if "blue" in pname.lower() else "Green"
            title = f"Gatsby Treatment Hair Cream 125g - {color_suffix}"
            desc = f"<p>Keep your hair neat, conditioned, and manageable with Gatsby Treatment Hair Cream 125g ({color_suffix}). Formulated for easy styling and healthy-looking shine.</p>"
            seo_t = f"Gatsby Treatment Hair Cream 125g - {color_suffix}"
            seo_d = f"Shop Gatsby Treatment Hair Cream 125g ({color_suffix}) for everyday hair styling and conditioning."
        elif art == "A Art 18":
            color_suffix = "Blue" if "blue" in pname.lower() else ("Pink" if "pink" in pname.lower() else "Purple")
            title = f"Nexton Baby Cologne 80ml - {color_suffix}"
            desc = f"<p>Keep your baby smelling fresh all day with Nexton Baby Cologne 80ml ({color_suffix}). Gentle, alcohol-free fragrance designed especially for delicate skin.</p>"
            seo_t = f"Nexton Baby Cologne 80ml - {color_suffix}"
            seo_d = f"Shop Nexton Baby Cologne 80ml ({color_suffix}). Mild, clean, and refreshing fragrance for babies and toddlers."
        elif art == "A Art 19":
            variant_name = "Blue (Original)" if "blue" in pname.lower() else "Pink (Blossoms)"
            title = f"Johnson's Baby Powder 200g - {variant_name}"
            desc = f"<p>Keep your baby's skin comfortably dry and soft with Johnson's Baby Powder 200g in {variant_name}. Clinically proven mild formula helps absorb excess moisture and reduce friction.</p>"
            seo_t = f"Johnson's Baby Powder 200g - {variant_name}"
            seo_d = f"Shop Johnson's Baby Powder 200g in {variant_name} for gentle moisture absorption and lasting freshness."
        elif art == "A Art 20":
            color_suffix = "Blue" if "blue" in pname.lower() else ("Pink" if "pink" in pname.lower() else "Green")
            title = f"Liock Anti-Rash Family Powder 200g - {color_suffix}"
            desc = f"<p>Protect your family from prickly heat and skin irritation with Liock Anti-Rash Family Powder 200g ({color_suffix}). Provides a soothing, cooling sensation that keeps skin fresh.</p>"
            seo_t = f"Liock Anti-Rash Family Powder 200g - {color_suffix}"
            seo_d = f"Shop Liock Anti-Rash Family Powder 200g ({color_suffix}) for effective rash relief and daily cooling protection."
        elif art == "A Art 21":
            color_suffix = "Pink" if "pink" in pname.lower() else ("White" if "white" in pname.lower() else "Blue")
            title = f"Nexton Baby Powder 350g - {color_suffix}"
            desc = f"<p>Ensure gentle daily protection with Nexton Baby Powder 350g ({color_suffix}). Helps absorb wetness and prevents chafing for happy, comfortable babies.</p>"
            seo_t = f"Nexton Baby Powder 350g - {color_suffix}"
            seo_d = f"Shop Nexton Baby Powder 350g ({color_suffix}) for long-lasting dryness and gentle baby care."
        elif art == "A Art 26":
            scent_m = re.search(r'-\s*(.+)$', pname)
            scent = scent_m.group(1).strip() if scent_m else "Signature"
            title = f"Kliock Eau De Parfum 100ml - {scent}"
            desc = f"<p>Experience an alluring, long-lasting scent with Kliock Eau De Parfum 100ml in {scent}. Formulated to provide 8 to 9 hours of captivating fragrance suitable for both him and her.</p>"
            seo_t = f"Kliock Perfume 100ml - {scent}"
            seo_d = f"Shop Kliock Eau De Parfum 100ml in {scent}. Long-lasting unisex fragrance with sophisticated notes."
        elif art == "A Art 27":
            scent_m = re.search(r'-\s*(.+)$', pname)
            scent = scent_m.group(1).strip() if scent_m else "Signature"
            title = f"Inertia Scents Eau De Parfum 100ml - {scent}"
            desc = f"<p>Elevate your personal aroma with Inertia Scents Signature Collection Eau De Parfum 100ml in {scent}. Delivers a refined, long-wearing fragrance lasting 8 to 9 hours.</p>"
            seo_t = f"Inertia Scents 100ml - {scent}"
            seo_d = f"Shop Inertia Scents Eau De Parfum 100ml in {scent}. Signature edition with premium aromatic profile."
        elif art == "A Art 28":
            scent_m = re.search(r'-\s*(.+)$', pname)
            scent = scent_m.group(1).strip() if scent_m else "Premium"
            title = f"Inertia Scents Eau De Parfum 100ml - {scent} (Premium Edition)"
            desc = f"<p>Discover luxurious fragrance with Inertia Scents Premium Edition Eau De Parfum 100ml in {scent}. A harmonious blend of aromatic notes crafted for elegance and charm.</p>"
            seo_t = f"Inertia Scents 100ml - {scent} Premium"
            seo_d = f"Shop Inertia Scents Premium Edition 100ml in {scent}. High-performance fragrance with enduring sillage."
        elif art == "A Art 29":
            scent_m = re.search(r'-\s*(.+)$', pname)
            scent = scent_m.group(1).strip() if scent_m else "Classic"
            title = f"Dorall Collection Men's Perfume 100ml - {scent}"
            desc = f"<p>Make a bold statement with Dorall Collection Men's Perfume 100ml in {scent}. Delivers an enduring masculine scent with 8 to 10 hours of projection and presence.</p>"
            seo_t = f"Dorall Collection Men's Perfume 100ml - {scent}"
            seo_d = f"Shop Dorall Collection Men's Perfume 100ml in {scent}. Distinctive men's fragrance lasting 8 to 10 hours."
        elif art == "A Art 30":
            scent_m = re.search(r'-\s*(.+)$', pname)
            scent = scent_m.group(1).strip() if scent_m else "Classic"
            title = f"MHS Guys Body Spray 200ml - {scent.capitalize()}"
            desc = f"<p>Stay energized and confident all day with MHS Guys Body Spray 200ml in {scent.capitalize()}. Formulated to deliver 5 to 7 hours of invigorating freshness.</p>"
            seo_t = f"MHS Guys Body Spray 200ml - {scent.capitalize()}"
            seo_d = f"Shop MHS Guys Body Spray 200ml in {scent.capitalize()}. Fast-drying, all-over body spray with long-lasting freshness."
        else:
            title = base_title if base_title else pname
            desc = base_desc if base_desc else f"<p>{title}. High quality personal care product.</p>"
            seo_t = base_seo_t if base_seo_t else title
            seo_d = base_seo_d if base_seo_d else f"Shop {title} online at Win Bachat."
            
        title = clean_text(title)
        desc = clean_text(desc)
        seo_t = clean_text(seo_t)
        seo_d = clean_text(seo_d)
        
        if not desc.startswith("<p>"):
            desc = f"<p>{desc}</p>"
            
        # Unique Handle Generation
        handle = slugify(title)
        if handle in used_handles:
            handle = f"{handle}-{s_no}"
        used_handles.add(handle)
        
        # Tags construction
        tags_list = ["Cosmetics", "Win Bachat", "AA Dot Store"]
        if item["cat"]:
            tags_list.append(item["cat"])
        if sub_cat and sub_cat not in tags_list:
            tags_list.append(sub_cat)
            
        # Extract Brand
        brand = None
        for b in ["Labello", "Enchanteur", "Creme 21", "Vaseline", "Chirss", "Huda Moji", "Aifone",
                  "Enzo", "Wokali", "Derma Rich", "Keratin", "Nitro", "Gatsby", "Nexton", "Johnson's", "Johnsons", "Liock", "Kliock", "Inertia", "Dorall", "MHS Guys"]:
            if b.lower() in title.lower() or b.lower() in pname.lower():
                brand = b.replace("Johnsons", "Johnson's")
                break
        if brand and brand not in tags_list:
            tags_list.append(brand)
            
        # Fragrance Gender Categorization (Men Perfume / Women Perfume)
        if art in ["A Art 26", "A Art 27", "A Art 28", "A Art 29", "A Art 30"]:
            scent_clean = pname.split("-")[-1].strip().lower()
            women_keywords = ["women", "damsel", "princes", "pink", "skin", "yara", "blissberry", "sara qael", "romantic", "secrecy", "memories", "red secret", "purple", "now and ever", "engross", "on my mind", "pristine", "desire", "radiant"]
            men_keywords = ["guys", "dorall", "offender", "islanders", "hunter", "suave", "hawas", "dirham", "beckham", "dinar", "ases", "azure", "have it", "fakhar", "marine", "vintage", "simple", "sumthin", "dc4u", "ivk", "opinion", "hunted", "wild", "black", "brown", "green", "orange", "blue"]
            
            is_unisex = any(u in scent_clean for u in ["divine", "ajwad", "whiteoud", "bakhoor"])
            is_w = any(w in scent_clean for w in women_keywords) or is_unisex
            has_men_word = bool(re.search(r'\b(men|man)\b', scent_clean))
            is_m = any(m in scent_clean for m in men_keywords) or has_men_word or is_unisex or art == "A Art 30"
            
            if not is_w and not is_m:
                is_m = True
                
            if is_w:
                tags_list.extend(["Women Perfume", "Women's Perfume", "Women Fragrance"])
            if is_m:
                tags_list.extend(["Men Perfume", "Men's Perfume", "Men Fragrance"])
            
        tags_str = ", ".join(dict.fromkeys(tags_list))
        
        # Images for this product
        folder_imgs = art_images.get(art, [])
        matched_imgs = []
        if len(folder_imgs) > 1:
            p_lower = pname.lower()
            for img in folder_imgs:
                orig_lower = img["original_name"].lower()
                colors = ["pink", "blue", "green", "white", "purple", "yellow", "black", "orange", "small", "large"]
                for c in colors:
                    if c in p_lower and c in orig_lower:
                        matched_imgs.append(img)
                        break
        if not matched_imgs:
            matched_imgs = folder_imgs
            
        prod_category = get_product_category(item["cat"], sub_cat, item["product_name"])
        prod_type = get_product_type(item["cat"], sub_cat)
        
        products.append({
            "s_no": s_no,
            "sku": sku,
            "art": art,
            "handle": handle,
            "title": title,
            "body_html": desc,
            "vendor": "Win Bachat",
            "category": prod_category,
            "type": prod_type,
            "tags": tags_str,
            "published": "true",
            "option1_name": "Title",
            "option1_value": "Default Title",
            "grams": weight_grams,
            "price": f"{price:.2f}",
            "cap_price": f"{cap_price:.2f}",
            "qty": qty,
            "barcode": "",
            "seo_title": seo_t,
            "seo_desc": seo_d,
            "status": "active",
            "images": matched_imgs,
            "original_name": pname,
            "original_art": art
        })
        
    print(f"Generated data structures for {len(products)} products.")
    
    # 1. Write WinBachat_AA_Dot_Store_Shopify_Import.csv
    with open(AA_SHOPIFY_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(SHOPIFY_HEADERS)
        
        for p in products:
            imgs = p["images"]
            primary_src = imgs[0]["url"] if imgs else ""
            
            # Row 1: Main product row
            writer.writerow([
                p["handle"],
                p["title"],
                p["body_html"],
                p["vendor"],
                p["category"],
                p["type"],
                p["tags"],
                p["published"],
                p["option1_name"],
                p["option1_value"],
                p["sku"],
                p["grams"],
                "shopify",
                "deny",
                "manual",
                p["price"],
                p["cap_price"],
                "true",
                "false",
                p["barcode"],
                primary_src,
                "1" if primary_src else "",
                p["title"] if primary_src else "",
                "false",
                p["seo_title"],
                p["seo_desc"],
                p["status"]
            ])
            
            # Supplementary image rows
            if len(imgs) > 1:
                for pos, img in enumerate(imgs[1:], start=2):
                    writer.writerow([
                        p["handle"],
                        "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                        img["url"],
                        str(pos),
                        f"{p['title']} - View {pos}",
                        "", "", "", ""
                    ])
                    
    print(f"Saved {AA_SHOPIFY_CSV}")
    
    # 2. Write WinBachat_AA_Dot_Store_Inventory_Import.csv using official 19-column template
    INVENTORY_HEADERS = [
        "Handle", "Title", "Option1 Name", "Option1 Value", "Option2 Name",
        "Option2 Value", "Option3 Name", "Option3 Value", "SKU", "HS Code",
        "COO", "Location", "Bin name", "Incoming (not editable)",
        "Unavailable (not editable)", "Committed (not editable)",
        "Available (not editable)", "On hand (current)", "On hand (new)"
    ]
    with open(AA_INVENTORY_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(INVENTORY_HEADERS)
        for p in products:
            writer.writerow([
                p["handle"],
                p["title"],
                "Title",
                "Default Title",
                "", "", "", "",
                p["sku"],
                "", "",
                "Win Bachat",
                "",
                "0", "0", "0",
                str(p["qty"]),
                "0",
                str(p["qty"])
            ])
    print(f"Saved {AA_INVENTORY_CSV}")
    
    # Also update/create master consolidated inventory CSV
    update_consolidated_inventory(products, INVENTORY_HEADERS)
    
    # 3. Create Multi-Tab Review Workbook
    create_review_workbook(products)
    
    # 4. Update Consolidated Master CSV
    update_consolidated_master(products)

def create_review_workbook(products):
    wb = openpyxl.Workbook()
    # Sheet 1: Catalog Summary
    ws_summary = wb.active
    ws_summary.title = "Catalog Summary"
    ws_summary.views.sheetView[0].showGridLines = True
    
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    zebra_fill = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    
    headers = [
        "S.No", "SKU", "ART Code", "Product Title", "Original Name in Sheet",
        "Category", "Sub-Category", "MRP (Rs.)", "Compare-At (+30%)", "Stock QTY",
        "Weight (g)", "Images Count", "Status"
    ]
    ws_summary.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws_summary.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    for idx, p in enumerate(products, start=2):
        row = [
            p["s_no"],
            p["sku"],
            p["art"],
            p["title"],
            p["original_name"],
            p["category"].split(" > ")[-1],
            p["type"],
            float(p["price"]),
            float(p["cap_price"]),
            p["qty"],
            p["grams"],
            len(p["images"]),
            p["status"].capitalize()
        ]
        ws_summary.append(row)
        for col_idx in range(1, len(headers) + 1):
            cell = ws_summary.cell(row=idx, column=col_idx)
            cell.border = thin_border
            if idx % 2 == 1:
                cell.fill = zebra_fill
            if col_idx in (1, 8, 9, 10, 11, 12):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (2, 3, 13):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
                
    for col in ws_summary.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_summary.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)
        
    # Sheet 2: Discrepancy & Audit Log
    ws_audit = wb.create_sheet(title="Discrepancy Audit Log")
    ws_audit.views.sheetView[0].showGridLines = True
    audit_headers = ["Item / ART", "Type of Issue", "Original State in Sheet", "Resolution Applied", "Rationale"]
    ws_audit.append(audit_headers)
    for col_idx in range(1, len(audit_headers) + 1):
        cell = ws_audit.cell(row=1, column=col_idx)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    audit_entries = [
        ("Row 41 (S.No 41) / A Art 23", "Title / Brand Mismatch", "Product Title = 'Liock Baby Oil 60ml & 120ml'", "Corrected to 'Johnson\'s Baby Oil 200ml'", "Photo and Product Name explicitly show Johnson\'s Baby Oil 200ml"),
        ("Row 42 (S.No 42) / A Art 23", "Missing Sub-Row Title & Description", "Title = None, Desc = None", "Created 'Johnson\'s Baby Oil 100ml' with complete description", "Photo shows 100ml bottle alongside 200ml"),
        ("Row 41 (S.No 41) / A Art 23", "Compound Weight Field", "Weight = '0.055 kg / 0.110 kg'", "Assigned 110g to 200ml variant and 55g to 100ml variant", "Shopify requires single numeric float per variant"),
        ("Row 39-41 (S.No 38-40) / A Art 22", "Product Title Mismatch", "Title = 'Liock Baby Shampoo Rich Moisture'", "Corrected to 'Liock Baby Lotion 100ml' (Pink, Blue, Yellow)", "Disk images and Product Name show baby lotions, not shampoo"),
        ("Row 44 (S.No 43) / A Art 24", "One-Row Shift in Title", "Title = 'Johnson\'s Baby Oil 200ml'", "Corrected to 'Nexton Baby Jelly 180ml'", "Disk image and Product Name are Nexton Baby Jelly"),
        ("Rows 28-30 (S.No 27-29) / A Art 18", "Blank Sub CATEGORY", "Sub CATEGORY = None", "Imputed 'Baby Cologne'", "Prevents blank collection filters"),
        ("Rows 44-46 (S.No 43-45) / A Art 24-25", "Blank Sub CATEGORY", "Sub CATEGORY = None", "Imputed 'Baby Jelly'", "Maintains clean hierarchical collection tags"),
        ("All 80 Sub-Rows across 14 ARTs", "Variant Architecture Consolidation", "Title/Desc/Weight = None", "Populated complete standalone product titles, inherited descriptions, and unique handles", "Ensures all 110 products are live, searchable, and fully documented"),
        ("Dorall Perfumes (A Art 29, 26 items)", "Shared Group Photos Only", "26 scents listed; 7 group photos on disk (no individual bottle shots)", "Published Active as individual listings with shared group gallery", "Per store owner policy: kept active while awaiting client individual pack shots"),
        ("Guys Body Spray (A Art 30, 8 items)", "Shared Group Photos Only", "8 fragrances listed; 1 group photo on disk", "Published Active as individual listings with shared group photo", "Per store owner policy: kept active with shared group shot"),
        ("Kliock Perfumes (A Art 26, 6 items)", "Shared Group Photos Only", "6 scents listed; 1 group photo on disk", "Published Active as individual listings with shared group photo", "Per store owner policy: kept active with shared group shot"),
        ("Inertia Perfumes (A Art 27 & 28, 25 items)", "Shared Group Photos Only", "25 scents listed; 5 group photos on disk", "Published Active as individual listings with shared group photos", "Per store owner policy: kept active with shared group shots")
    ]
    for idx, entry in enumerate(audit_entries, start=2):
        ws_audit.append(entry)
        for col_idx in range(1, len(audit_headers) + 1):
            cell = ws_audit.cell(row=idx, column=col_idx)
            cell.border = thin_border
            if idx % 2 == 1:
                cell.fill = zebra_fill
                
    for col in ws_audit.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_audit.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 60)
        
    wb.save(AA_REVIEW_XLSX)
    print(f"Saved {AA_REVIEW_XLSX}")

def update_consolidated_master(new_products):
    existing_rows = []
    base_file = "WinBachat_Combined_Shopify_Import.csv"
    if os.path.exists(base_file):
        with open(base_file, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            existing_rows = list(reader)
    elif os.path.exists(CONSOLIDATED_MASTER_CSV):
        with open(CONSOLIDATED_MASTER_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            # Filter out any old AASTORE rows if present
            existing_rows = [r for r in reader if not ('MRT-WB-AASTORE' in r[10] or 'aastore' in r[0].lower())]
            
    print(f"Base products rows loaded: {len(existing_rows)}")
    
    aa_rows = []
    for p in new_products:
        imgs = p["images"]
        primary_src = imgs[0]["url"] if imgs else ""
        aa_rows.append([
            p["handle"],
            p["title"],
            p["body_html"],
            p["vendor"],
            p["category"],
            p["type"],
            p["tags"],
            p["published"],
            p["option1_name"],
            p["option1_value"],
            p["sku"],
            p["grams"],
            "shopify",
            "deny",
            "manual",
            p["price"],
            p["cap_price"],
            "true",
            "false",
            p["barcode"],
            primary_src,
            "1" if primary_src else "",
            p["title"] if primary_src else "",
            "false",
            p["seo_title"],
            p["seo_desc"],
            p["status"]
        ])
        if len(imgs) > 1:
            for pos, img in enumerate(imgs[1:], start=2):
                aa_rows.append([
                    p["handle"],
                    "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                    img["url"],
                    str(pos),
                    f"{p['title']} - View {pos}",
                    "", "", "", ""
                ])
                
    all_master_rows = existing_rows + aa_rows
    with open(CONSOLIDATED_MASTER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(SHOPIFY_HEADERS)
        writer.writerows(all_master_rows)
        
    print(f"Consolidated master CSV updated: {len(all_master_rows)} total rows across Westpoint, MTS Gardening, and AA Dot Store.")

def update_consolidated_inventory(new_products, headers):
    existing_inv_rows = []
    base_inv_file = "WinBachat_New_Batches_Inventory_Import.csv"
    if os.path.exists(base_inv_file):
        with open(base_inv_file, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            h = next(reader)
            # Keep non-AASTORE rows
            existing_inv_rows = [r for r in reader if not ('MRT-WB-AASTORE' in r[8] or 'aastore' in r[0].lower())]
            
    print(f"Base inventory rows loaded: {len(existing_inv_rows)}")
    
    aa_inv_rows = []
    for p in new_products:
        aa_inv_rows.append([
            p["handle"],
            p["title"],
            "Title",
            "Default Title",
            "", "", "", "",
            p["sku"],
            "", "",
            "Win Bachat",
            "",
            "0", "0", "0",
            str(p["qty"]),
            "0",
            str(p["qty"])
        ])
        
    all_inv_rows = existing_inv_rows + aa_inv_rows
    # Save both WinBachat_New_Batches_Inventory_Import.csv and WinBachat_Products_Inventory_Import.csv
    for out_name in ["WinBachat_New_Batches_Inventory_Import.csv", "WinBachat_Products_Inventory_Import.csv"]:
        with open(out_name, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(all_inv_rows)
            
    print(f"Consolidated master inventory updated ({len(all_inv_rows)} items) across Westpoint, MTS Gardening, and AA Dot Store.")

if __name__ == "__main__":
    main()
