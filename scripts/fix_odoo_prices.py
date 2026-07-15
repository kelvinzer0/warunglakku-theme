#!/usr/bin/env python3
"""Fix 17 products in Odoo that have list_price = Rp 1,000,000 (should be Rp 1,000).

Root cause: WA catalog price "1000000" (priceAmount1000 = Rp 1,000 × 1000) was not
divided by 1000 due to `> 1000000` (strict greater than) threshold in the workflow.
"""
import json
import urllib.request

ODOO_URL = "https://warunglakku.com/jsonrpc"
ODOO_DB = "warunglakku-odoo"
ODOO_UID = 2
ODOO_PASS = "kelvin123"


def rpc(model, method, args_list):
    body = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [ODOO_DB, ODOO_UID, ODOO_PASS, model, method, args_list]
        },
        "id": 1,
    }
    req = urllib.request.Request(ODOO_URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["result"]


# Find all products with the bug: list_price = 1,000,000 (synced from WA)
products = rpc("product.product", "search_read",
    [[["default_code", "like", "WA-"], ["list_price", "=", 1000000]],
     ["id", "name", "default_code", "list_price"]])

print(f"Found {len(products)} products with bug (list_price = Rp 1,000,000):")
for p in products:
    print(f"  id={p['id']:4d} | {p['name'][:40]:40s} | {p['default_code']}")

if not products:
    print("Nothing to fix.")
    raise SystemExit(0)

# Update all to Rp 1,000
ids = [p["id"] for p in products]
new_price = 1000.0
print(f"\n→ Bulk updating {len(ids)} products to Rp {new_price:,.0f}...")
result = rpc("product.product", "write", [ids, {"list_price": new_price}])
print(f"  write result: {result}")

# Verify
print("\n→ Verifying...")
verify = rpc("product.product", "search_read",
    [[["id", "in", ids]], ["id", "name", "list_price"]])
print(f"  Verified {len(verify)} products after update:")
for p in sorted(verify, key=lambda x: x["id"]):
    print(f"  id={p['id']:4d} | {p['name'][:40]:40s} | Rp {p['list_price']:,.0f}")
