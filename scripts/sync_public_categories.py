#!/usr/bin/env python3
"""Sync product.template public_categ_ids based on WA collection mapping.

Fetches collections from Evolution API getCollections, maps each product
to its collection name, then matches to product.public.category by name
(case-insensitive). Sets public_categ_ids on each product.template.

This is a one-time sync script. After running, the /shop filter chips
will show product counts per category, and clicking a chip will filter
products correctly.
"""
import json
import urllib.request
import ssl
import re

ODOO_URL = "https://warunglakku.com/jsonrpc"
ODOO_DB = "warunglakku-odoo"
ODOO_UID = 2
ODOO_PASS = "kelvin123"

EVO_URL = "https://evolution.warunglakku.com/business/getCollections/Warung%20Lakku"
EVO_KEY = "429683C4C977415CAAFCCE10F7D57E11"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def rpc(model, method, args):
    body = {
        "jsonrpc": "2.0", "method": "call",
        "params": {"service": "object", "method": "execute_kw",
                   "args": [ODOO_DB, ODOO_UID, ODOO_PASS, model, method, args]},
        "id": 1,
    }
    req = urllib.request.Request(ODOO_URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        out = json.loads(resp.read().decode())
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["result"]


def fetch_wa_collections():
    """Fetch WA collections from Evolution API. Returns {product_id: collection_name}."""
    data = json.dumps({"provider": "browser", "limit": 200}).encode()
    req = urllib.request.Request(EVO_URL, data=data, method="POST", headers={
        "apikey": EVO_KEY,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
        result = json.loads(resp.read().decode())

    mapping = {}
    collections = result.get("collections", [])
    print(f"  Fetched {len(collections)} collections, {result.get('totalProductsMapped', 0)} products mapped")

    for col in collections:
        col_name = col.get("name", "")
        for p in col.get("products", []):
            pid = str(p.get("id", ""))
            if pid and col_name:
                mapping[pid] = col_name
    print(f"  Built mapping: {len(mapping)} products → collections")
    return mapping


def main():
    print("=" * 70)
    print("Sync product.public.category to product.template via WA collections")
    print("=" * 70)

    # Step 1: Fetch WA collections
    print("\n[1/4] Fetching WA collections from Evolution API...")
    wa_mapping = fetch_wa_collections()

    # Step 2: Get public categories from Odoo
    print("\n[2/4] Fetching product.public.category from Odoo...")
    pub_ids = rpc("product.public.category", "search", [[]])
    pub_cats = rpc("product.public.category", "read", [pub_ids, ["id", "name"]])
    # Build name → id map (case-insensitive)
    name_to_id = {}
    for c in pub_cats:
        name_to_id[c["name"].lower()] = c["id"]
    print(f"  Found {len(pub_cats)} public categories:")
    for c in pub_cats:
        print(f"    id={c['id']} name={c['name']}")

    # Step 3: Get published products from Odoo
    print("\n[3/4] Fetching published products...")
    pub_prod_ids = rpc("product.template", "search", [[["is_published", "=", True]]])
    prods = rpc("product.template", "read", [pub_prod_ids, ["id", "name", "default_code"]])
    print(f"  Found {len(prods)} published products")

    # Step 4: Link each product to its public category
    print("\n[4/4] Linking products to public categories...")
    linked = 0
    no_match = 0
    no_wa_id = 0

    for p in prods:
        dc = p.get("default_code", "")
        # default_code format: WA-{wa_id}
        wa_id = dc[3:] if dc.startswith("WA-") else ""
        if not wa_id:
            no_wa_id += 1
            continue

        col_name = wa_mapping.get(wa_id, "")
        if not col_name:
            no_match += 1
            continue

        # Match collection name to public category (case-insensitive)
        pub_cat_id = name_to_id.get(col_name.lower())
        if not pub_cat_id:
            print(f"  ⚠ No public category match for '{col_name}' (product: {p['name']})")
            no_match += 1
            continue

        # Set public_categ_ids (replace)
        rpc("product.template", "write", [[p["id"]], {"public_categ_ids": [[6, 0, [pub_cat_id]]]}])
        linked += 1

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total published:     {len(prods)}")
    print(f"  ✓ Linked to category: {linked}")
    print(f"  ✗ No WA collection:   {no_match}")
    print(f"  ✗ No default_code:    {no_wa_id}")


if __name__ == "__main__":
    main()
