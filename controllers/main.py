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
  Word frequencies:
    kerupuk → appears in 5 products
    bakso   → appears in 3 products
    seblak  → appears in 4 products (filtered as stopword since it's
              the category name and provides no discrimination)
  Result:
    Products containing 'kerupuk' (5) get higher score than 'bakso' (3)
    A 'Kerupuk Bawang' product ranks above 'Bakso Keju'
    'Telur' (1 product, score=0) ranks last (alphabetical within score=0)

When user explicitly picks a sort (?order=list_price_asc),
the similarity sort is BYPASSED and Odoo's native sort applies.

Implementation:
  Pre-compute sorted product IDs in Python, then pass a CASE WHEN
  SQL expression as the `order` parameter via post['order'].
  Odoo's _get_search_order(post) returns:
      'is_published desc, <post[order]>, id desc'
  so our CASE WHEN sits between is_published and id — perfect for
  overriding the default sort while preserving pagination, rendering,
  wishlist, comparison list, attribute filters, etc.

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
# Note: the category NAME itself (e.g. "Seblak") is naturally a stopword
# here because we filter it explicitly below. But common words like
# "dan", "atau" need to be in this list.
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

    Args:
        name: product name string
        extra_stopwords: optional set of words to also filter
                         (e.g. the current category name)

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


def build_similarity_order_sql(sorted_ids):
    """Build a SQL ORDER BY CASE expression for pre-sorted IDs.

    Returns SQL like:
        CASE id WHEN 42 THEN 0 WHEN 18 THEN 1 ... ELSE 999999 END, name

    PostgreSQL evaluates this as a per-row rank, so the result set is
    returned in our pre-computed order.

    Args:
        sorted_ids: list of product.template ids in desired order

    Returns:
        str: SQL ORDER BY clause value (without the 'ORDER BY' keyword)
    """
    if not sorted_ids:
        return None

    # Cap CASE WHEN length to avoid SQL queries that are too large.
    # PostgreSQL handles long CASE expressions fine, but a query with
    # 5000+ WHEN clauses is slow to parse. 1000 is a safe upper bound.
    capped_ids = sorted_ids[:1000]
    offset = len(capped_ids)

    cases = ' '.join(
        'WHEN %d THEN %d' % (pid, idx)
        for idx, pid in enumerate(capped_ids)
    )
    # ELSE 1000000 pushes any product not in our list to the end.
    # Secondary sort by name provides alphabetical fallback.
    return 'CASE id %s ELSE 1000000 END, name' % cases


class _LightweightProduct(object):
    """Tiny placeholder for product.template records when scoring.

    We only need .id and .name — using the full recordset would
    trigger lazy loading of many fields we don't use.
    """
    __slots__ = ('id', 'name')

    def __init__(self, pid, name):
        self.id = pid
        self.name = name


class WLSimilaritySortWebsiteSale(WebsiteSale):
    """Override /shop to apply similarity-based default sort.

    The override intercepts shop() BEFORE Odoo does its product search.
    If user didn't request an explicit sort, we:
      1. Build the same domain Odoo would build (via _get_shop_domain)
      2. Fetch ALL matching product IDs + names
      3. Compute similarity scores
      4. Build CASE WHEN SQL
      5. Set post['order'] = our SQL
      6. Defer to super().shop() — Odoo's _get_search_order picks up
         our post['order'] and uses it in the actual SQL ORDER BY

    All Odoo features (pagination, rendering, wishlist, comparison,
    attribute filters, etc.) work unchanged.
    """

    @http.route()
    def shop(self, page=0, category=None, search='', ppg=False, **post):
        # If user explicitly chose a sort, defer to Odoo entirely
        if post.get('order'):
            return super().shop(page=page, category=category, search=search,
                                ppg=ppg, **post)

        try:
            # === Resolve category object (Odoo does this in shop()) ===
            Category = request.env['product.public.category']
            cat_obj = None
            if category:
                cat_obj = Category.search([('id', '=', int(category))], limit=1)

            # === Build the same domain Odoo would build ===
            # Reuse Odoo's _get_shop_domain helper so we don't reinvent
            # filtering logic (attrib, search, category all respected).
            attrib_list = request.httprequest.args.getlist('attrib')
            attrib_values = [
                [int(v) for x in v.split('-')]
                for v in attrib_list
                if v and '-' in v
            ]
            # Fix: each attrib value should be [int(attr_id), int(value_id)]
            attrib_values = []
            for v in attrib_list:
                if v and '-' in v:
                    parts = v.split('-')
                    try:
                        attrib_values.append([int(parts[0]), int(parts[1])])
                    except (ValueError, IndexError):
                        continue

            domain = self._get_shop_domain(search, cat_obj, attrib_values)

            # === Fetch ALL matching products (just IDs + names) ===
            Product = request.env['product.template'].with_context(bin_size=True)
            matching_products = Product.search(domain)
            all_ids = matching_products.ids

            if not all_ids:
                # Empty result — defer to Odoo's empty-state handling
                return super().shop(page=page, category=category, search=search,
                                    ppg=ppg, **post)

            # Read only id + name — minimal DB load for scoring
            products_data = matching_products.read(['name'])

            # Build lightweight objects for scoring
            light_products = [
                _LightweightProduct(d['id'], d.get('name') or '')
                for d in products_data
            ]

            # === Compute similarity scores ===
            # Optional: treat the category name as a stopword when browsing
            # a category listing (otherwise every product in /shop?category=seblak
            # would get +N for the word 'seblak', flattening the score).
            extra_stop = frozenset()
            if cat_obj and cat_obj.name:
                # Lowercase category name + tokenize it (it might be multi-word)
                extra_stop = frozenset(_WORD_RE.findall(cat_obj.name.lower()))

            scores = compute_similarity_scores(light_products, extra_stop)

            # === Sort by (score DESC, name_lower ASC) ===
            name_lower_map = {d['id']: (d.get('name') or '').lower()
                              for d in products_data}
            sorted_ids = sorted(
                all_ids,
                key=lambda pid: (-scores.get(pid, 0),
                                 name_lower_map.get(pid, ''))
            )

            # === Build CASE WHEN SQL and pass to super via post['order'] ===
            order_sql = build_similarity_order_sql(sorted_ids)
            if order_sql:
                post['order'] = order_sql

            _logger.debug(
                '[WL Similarity Sort] %d products scored (cat=%s, search=%r). '
                'Top 5: %s',
                len(sorted_ids),
                cat_obj.name if cat_obj else None,
                search,
                [(pid, scores.get(pid, 0)) for pid in sorted_ids[:5]]
            )

        except Exception as e:
            # If anything goes wrong, fall back to Odoo's default sort
            # so the page still loads. We log the error for debugging.
            _logger.warning(
                '[WL Similarity Sort] Failed (%s), falling back to Odoo default',
                e, exc_info=True
            )
            # Make sure no partial order is set
            post.pop('order', None)

        return super().shop(page=page, category=category, search=search,
                            ppg=ppg, **post)
