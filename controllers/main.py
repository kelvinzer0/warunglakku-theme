# -*- coding: utf-8 -*-
# Part of Warung Lakku Theme. See LICENSE file for full copyright and licensing details.
"""
Custom /shop controller with similarity-based default sort.

When user opens /shop WITHOUT explicit `order` URL parameter,
products are sorted by "name similarity score" instead of Odoo's
default (shop_default_sort).

Algorithm:
  1. Tokenize each product name into words (lowercase, strip punctuation)
  2. Build word frequency map: for each word, count how many OTHER
     products in the current listing contain it
  3. Score each product = sum of (other-product counts) across its words
  4. Sort by (score DESC, name ASC) — products with words that appear
     frequently across the catalog come first; ties broken alphabetically

Example (Seblak category with 22 products):
  Word frequencies (with 'seblak' filtered as stopword since it's
  the category name and would inflate every product's score equally):
    'lv'      → appears in 6 products  (lv0, lv1, lv2, lv4, lv5, lv3)
    'jamur'   → appears in 4 products  (enoki, enoki 1 bungkus, kuping, shimeji)
    'kerupuk' → appears in 4 products  (bawang, bintang, oren, uyel)
    'bakso'   → appears in 2 products  (Bakso Keju, Tahu bakso)
    'telur'   → appears in 1 product   (just Telur)
  Result:
    'Extra pedas lv3' (score 7: lv=5 + pedas=2) ranks above
    'Telur' (score 0: telur is unique)

When user explicitly picks a sort (?order=list_price_asc),
the similarity sort is BYPASSED and Odoo's native sort applies.

Implementation:
  Override `_shop_lookup_products()` to call super() (which handles
  domain building, fuzzy search, attribute filtering — all unchanged),
  then RE-SORT the returned product recordset in Python by similarity
  score. Pagination in shop() then slices this re-sorted recordset.

  We tried passing CASE WHEN SQL via post['order'], but Odoo's ORM
  validates the order string via OrderBy parser and rejects raw SQL.

Author: Kelvin Yuli Andrian
Since:  v17.0.3.10.70
"""

import re
import logging

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)

# Match word characters (Unicode-aware, includes accented letters).
# Excludes digits and underscores via [^\W\d_] — pure letters only.
_WORD_RE = re.compile(r'[^\W\d_]+', re.UNICODE)

# Stopwords: common Indonesian + English words + WL-specific noise.
# These don't carry product meaning and would skew the frequency map.
_STOPWORDS = frozenset({
    # Indonesian
    'dan', 'atau', 'di', 'ke', 'dari', 'untuk', 'dengan', 'yang', 'ini',
    'itu', 'ada', 'tidak', 'juga', 'akan', 'sudah', 'bisa', 'oleh',
    'pada', 'bagi', 'tentang', 'seperti', 'agar', 'supaya', 'karena',
    'sehingga', 'tetapi', 'namun', 'kecuali', 'selain',
    # English
    'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'this', 'that', 'these', 'those', 'it', 'its',
    # Generic descriptors (units / packaging)
    'pcs', 'pc', 'set', 'pack', 'paket', 'bungkus', 'bks', 'gr', 'kg',
    'ml', 'l', 'liter', 'buah', 'porsi',
    # WL-specific noise (default_code prefix etc.)
    'wa',
})


def tokenize(name, extra_stopwords=None):
    """Split product name into meaningful word tokens (lowercase).

    - Strips punctuation and digits-only tokens
    - Filters stopwords and 1-char tokens
    - Returns a list of UNIQUE words per product

    Examples:
      >>> tokenize("Bakso Keju 1 Bungkus (WA-123)")
      ['bakso', 'keju']
      >>> tokenize("Seblak Komplit")
      ['seblak', 'komplit']
    """
    if not name:
        return []
    words = _WORD_RE.findall(name.lower())
    stop = _STOPWORDS
    if extra_stopwords:
        stop = stop | extra_stopwords
    seen = set()
    result = []
    for w in words:
        if w in stop or len(w) < 2:
            continue
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result


def compute_similarity_scores(products, extra_stopwords=None):
    """Compute similarity score for each product.

    Score = sum of (number of OTHER products that share each word)

    A product with words that appear in many other products gets a
    higher score, pushing it toward the top of the listing.

    Args:
        products: iterable of lightweight objects with .id and .name
        extra_stopwords: optional set of words to filter from tokenization

    Returns:
        dict mapping product id → similarity score (int)
    """
    tokens_per_product = []  # list of (product_id, [words])
    word_to_product_ids = {}  # word -> set of product ids containing it

    for p in products:
        words = tokenize(p.name or '', extra_stopwords)
        tokens_per_product.append((p.id, words))
        for w in words:
            word_to_product_ids.setdefault(w, set()).add(p.id)

    scores = {}
    for pid, words in tokens_per_product:
        score = 0
        for w in words:
            # Count of OTHER products containing this word
            other_count = len(word_to_product_ids.get(w, set())) - 1
            if other_count > 0:
                score += other_count
        scores[pid] = score

    return scores


def sort_product_ids_by_similarity(products_data, extra_stopwords=None):
    """Sort product IDs by similarity score (DESC), then name (ASC).

    Args:
        products_data: list of dicts with 'id' and 'name' keys
                       (e.g. [{"id": 42, "name": "Bakso Keju"}, ...])
        extra_stopwords: optional set of words to filter from tokenization

    Returns:
        list of product IDs in similarity-sorted order
    """
    class _P:
        __slots__ = ('id', 'name')
        def __init__(self, pid, name):
            self.id = pid
            self.name = name

    products = [_P(d['id'], d.get('name') or '') for d in products_data]
    scores = compute_similarity_scores(products, extra_stopwords)
    name_lower_map = {p.id: (p.name or '').lower() for p in products}

    return sorted(
        [p.id for p in products],
        key=lambda pid: (-scores.get(pid, 0), name_lower_map.get(pid, ''))
    )


class WLSimilaritySortWebsiteSale(WebsiteSale):
    """Override /shop to apply similarity-based default sort.

    Strategy: override `_shop_lookup_products()` to call super() (which
    handles all of Odoo's filtering, fuzzy search, attribute filtering
    unchanged), then re-sort the returned product recordset in Python
    using our similarity algorithm.

    The re-sorted recordset is returned to Odoo's shop(), which then
    paginates and renders it normally. Pagination will respect our
    new order because `search_product[offset:offset + ppg]` slices
    the recordset in its current order.
    """

    def _shop_lookup_products(self, attrib_set, options, post, search, website):
        """Override to re-sort products by similarity when no explicit sort.

        Flow:
          1. Call super() — gets `search_product` recordset in Odoo's
             default order (website_sequence desc, name asc, or whatever
             shop_default_sort is configured to).
          2. If user explicitly requested a sort via `post['order']`,
             return super()'s result unchanged.
          3. Otherwise:
             a. Read just the name field for all matching products
             b. Compute similarity scores
             c. Build sorted ID list
             d. Re-browse products in our sorted order
             e. Return re-sorted recordset (count stays the same)
        """
        # Call super to get the default-sorted recordset
        fuzzy_search_term, product_count, search_product = super()._shop_lookup_products(
            attrib_set, options, post, search, website
        )

        # If user explicitly chose a sort, defer to Odoo's order
        if post.get('order'):
            return fuzzy_search_term, product_count, search_product

        # If no products, nothing to sort
        if not search_product:
            return fuzzy_search_term, product_count, search_product

        try:
            # === Read names (minimal DB load) ===
            products_data = search_product.read(['name'])

            # === Build extra stopwords from current category name ===
            # When browsing /shop?category=seblak, every product has
            # 'seblak' in context, so it provides no discrimination.
            # We treat the category name as a stopword.
            extra_stop = frozenset()
            category = options.get('category') if isinstance(options, dict) else None
            if category and hasattr(category, 'name') and category.name:
                extra_stop = frozenset(_WORD_RE.findall(category.name.lower()))

            # === Sort IDs by similarity ===
            sorted_ids = sort_product_ids_by_similarity(products_data, extra_stop)

            # === Re-browse in sorted order ===
            # This preserves the same recordset (same count, same domain)
            # but with our custom order. Pagination in shop() will then
            # slice this recordset correctly.
            search_product = search_product.browse(sorted_ids)

            _logger.debug(
                '[WL Similarity Sort] %d products re-sorted. Top 5 IDs: %s',
                len(sorted_ids),
                sorted_ids[:5]
            )

        except Exception as e:
            # If anything fails, fall back to Odoo's default order
            # so the page still loads. Log for debugging.
            _logger.warning(
                '[WL Similarity Sort] Failed (%s), keeping Odoo default order',
                e, exc_info=True
            )

        return fuzzy_search_term, product_count, search_product
