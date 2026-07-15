#!/usr/bin/env python3
"""Re-trigger image sync for all WA-synced products with empty/null image_1920.

Strategy:
1. Query Odoo for product.product WHERE default_code LIKE 'WA-%' AND (image_1920 IS NULL OR image_1920 = '')
2. For each product, extract WA product ID from default_code (strip 'WA-' prefix)
3. Download image from Evolution API:
   - Try external URL: https://evolution.warunglakku.com/catalog-images/Warung-Lakku/{waId}.jpg
   - This URL is accessible from host via Cloudflare
4. Upload via JSON-RPC write to BOTH product.product (variant) and product.template
5. Verify by re-querying image_1920 size
"""
import json
import urllib.request
import urllib.error
import base64
import ssl
import time
import sys

# === Config ===
ODOO_URL = "https://warunglakku.com/jsonrpc"
ODOO_DB = "warunglakku-odoo"
ODOO_UID = 2
ODOO_PASS = "kelvin123"

# Evolution API - external URL accessible from host via Cloudflare
EVO_IMG_URL_TMPL = "https://evolution.warunglakku.com/catalog-images/Warung-Lakku/{wa_id}.jpg"

# Instance folder name uses hyphen instead of space
EVO_IMG_URL_ALT_TMPL = "https://evolution.warunglakku.com/catalog-images/Warung-Lakku/{wa_id}.jpg"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def rpc(model, method, args):
    body = {
        "jsonrpc": "2.0", "method": "call",
        "params": {"service": "object", "method": "execute_kw",
                   "args": [ODOO_DB, ODOO_UID, ODOO_PASS, model, method, args]},
        "id": 1,
    }
    req = urllib.request.Request(ODOO_URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=ssl_ctx) as resp:
            out = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:500]}")
    if "error" in out:
        raise RuntimeError(json.dumps(out["error"])[:500])
    return out["result"]


def download_image(wa_id):
    """Download image from Evolution API. Returns (bytes, None) or (None, error_msg)."""
    url = EVO_IMG_URL_TMPL.format(wa_id=wa_id)
    req = urllib.request.Request(url, headers={"User-Agent": "OdooImageSync/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            data = resp.read()
            if len(data) < 1000:
                return None, f"image too small ({len(data)} bytes, likely 404)"
            return data, None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "404 not found"
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)[:200]


def main():
    print("=" * 80)
    print("Re-sync images for WA products with empty image_1920")
    print("=" * 80)

    # Step 1: Find all WA products with empty/null image_1920
    print("\n[1/4] Querying Odoo for products with empty image...")
    products = rpc("product.product", "search_read",
        [[["default_code", "like", "WA-"], ["image_1920", "=", False]],
         ["id", "name", "default_code", "product_tmpl_id"], 0, 500])

    print(f"  Found {len(products)} products with null/empty image_1920")

    if not products:
        print("  Nothing to do - all WA products have images!")
        return

    # Show sample
    print(f"\n  Sample (first 10):")
    for p in products[:10]:
        tmpl_id = p.get("product_tmpl_id", [None])[0] if p.get("product_tmpl_id") else None
        print(f"    pp_id={p['id']:4d} | pt_id={tmpl_id} | {p['default_code']} | {p['name'][:40]}")
    if len(products) > 10:
        print(f"    ... and {len(products) - 10} more")

    # Step 2: For each, download + upload
    print(f"\n[2/4] Downloading from Evolution API and uploading to Odoo...")
    success = 0
    failed_download = 0
    failed_upload = 0
    skipped_no_tmpl = 0

    for i, p in enumerate(products, 1):
        pp_id = p["id"]
        default_code = p["default_code"]
        name = p["name"]
        # Strip 'WA-' prefix to get WA product ID
        wa_id = default_code[3:] if default_code.startswith("WA-") else default_code

        # Get product_tmpl_id
        pt_field = p.get("product_tmpl_id")
        tmpl_id = pt_field[0] if isinstance(pt_field, list) and pt_field else None

        # Progress
        if i % 10 == 0 or i == len(products):
            print(f"  Progress: {i}/{len(products)} (ok={success}, dl_fail={failed_download}, up_fail={failed_upload})")

        # Step 2a: Download image
        img_data, err = download_image(wa_id)
        if img_data is None:
            print(f"  [DL-FAIL] {default_code} {name[:30]} → {err}")
            failed_download += 1
            continue

        # Step 2b: Convert to base64
        b64 = base64.b64encode(img_data).decode("ascii")
        img_size_kb = len(img_data) / 1024

        # Step 2c: Write to product.product
        try:
            rpc("product.product", "write", [[pp_id], {"image_1920": b64}])
        except Exception as e:
            print(f"  [UP-FAIL-PP] {default_code} {name[:30]} → {str(e)[:200]}")
            failed_upload += 1
            continue

        # Step 2d: Write to product.template (if we have tmpl_id)
        if tmpl_id:
            try:
                rpc("product.template", "write", [[tmpl_id], {"image_1920": b64}])
            except Exception as e:
                print(f"  [UP-WARN-PT] {default_code} pt={tmpl_id} → {str(e)[:200]} (PP write OK)")
        else:
            skipped_no_tmpl += 1
            print(f"  [NO-TMPL] {default_code} {name[:30]} → no product_tmpl_id (PP write OK)")

        success += 1
        # Brief log every successful 25 items
        if success % 25 == 0:
            print(f"  ✓ {success} images uploaded so far ({img_size_kb:.0f} KB last)")

        # Small delay to not overwhelm Odoo
        time.sleep(0.1)

    # Step 3: Verify
    print(f"\n[3/4] Verifying images were uploaded...")
    still_empty = rpc("product.product", "search_read",
        [[["id", "in", [p["id"] for p in products]]], ["id", "name", "default_code", "image_1920"]])
    empty_count = sum(1 for p in still_empty if not p.get("image_1920"))
    print(f"  Out of {len(products)} processed, {empty_count} still have empty image")

    # Step 4: Summary
    print(f"\n[4/4] Summary:")
    print(f"  Total processed:     {len(products)}")
    print(f"  ✓ Success:           {success}")
    print(f"  ✗ Download failed:   {failed_download}")
    print(f"  ✗ Upload failed:     {failed_upload}")
    print(f"  ⚠ No template id:    {skipped_no_tmpl}")
    print(f"  Still empty:         {empty_count}")


if __name__ == "__main__":
    main()
