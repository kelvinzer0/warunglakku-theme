#!/usr/bin/env python3
"""
Unit tests for WL similarity sorting algorithm.

These tests verify the tokenize() + compute_similarity_scores() +
build_similarity_order_sql() functions in isolation, without needing
a running Odoo instance.

Run:  python3 tests/test_similarity_sort.py
"""
import os
import sys
import re as _re

# Make controllers/ importable when run standalone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Read controllers/main.py and exec just the algorithm section
# (we can't import the full module because it imports odoo which
# isn't available outside the Odoo container)
with open(os.path.join(os.path.dirname(__file__), '..', 'controllers', 'main.py')) as f:
    src = f.read()

# Extract only the algorithm section:
#   import re / import logging
#   ...
#   def build_similarity_order_sql(...)
# We stop BEFORE the line that starts 'class _LightweightProduct'
# and strip any odoo-importing lines.

# Find the algorithm section (from 'import re' to end of build_similarity_order_sql)
m = _re.search(
    r'(import re\nimport logging.*?return \'CASE id.*?ELSE 1000000 END, name\' % cases)\n',
    src, _re.DOTALL
)
algo_src = m.group(1)

# Strip any line that imports odoo
algo_src = '\n'.join(
    line for line in algo_src.split('\n')
    if not line.startswith('from odoo') and not line.startswith('import odoo')
)

ns = {}
exec(algo_src, ns)

tokenize = ns['tokenize']
compute_similarity_scores = ns['compute_similarity_scores']
build_similarity_order_sql = ns['build_similarity_order_sql']


class _P:
    """Lightweight product for testing."""
    __slots__ = ('id', 'name')
    def __init__(self, pid, name):
        self.id = pid
        self.name = name


def test_tokenize_basic():
    """tokenize should return lowercased letters-only tokens, no stopwords."""
    assert tokenize("Bakso Keju") == ['bakso', 'keju']
    assert tokenize("Seblak Komplit") == ['seblak', 'komplit']
    assert tokenize("Kerupuk Bawang Pedas Lv3") == ['kerupuk', 'bawang', 'pedas', 'lv']


def test_tokenize_strips_punctuation_and_digits():
    assert tokenize("Bakso Keju 1 Bungkus (WA-123)") == ['bakso', 'keju']
    assert tokenize("Telur Ceplok (2 butir)") == ['telur', 'ceplok', 'butir']


def test_tokenize_filters_stopwords():
    assert tokenize("Bakso dan Sosis") == ['bakso', 'sosis']
    assert tokenize("Mie dengan kuah") == ['mie', 'kuah']
    assert tokenize("the great bakso") == ['great', 'bakso']


def test_tokenize_filters_short_words():
    """1-char tokens are filtered."""
    assert tokenize("A I Bakso") == ['bakso']


def test_tokenize_dedupes_within_product():
    """A product containing 'bakso bakso' counts as 1 unique word."""
    assert tokenize("bakso bakso") == ['bakso']


def test_tokenize_empty():
    assert tokenize("") == []
    assert tokenize(None) == []


def test_tokenize_case_insensitive():
    assert tokenize("BAKSO") == ['bakso']
    assert tokenize("BakSo KeJu") == ['bakso', 'keju']


def test_tokenize_unicode():
    """Indonesian + accented letters should be preserved."""
    assert tokenize('café résumé') == ['café', 'résumé']
    assert tokenize('mie goreng') == ['mie', 'goreng']


def test_tokenize_extra_stopwords():
    """Caller can pass extra stopwords (e.g. category name)."""
    result = tokenize("Seblak Komplit", extra_stopwords=frozenset({'seblak'}))
    assert result == ['komplit']


def test_similarity_score_zero_for_unique_words():
    """Product with words no other product has → score = 0."""
    products = [
        _P(1, "Telur Asin"),
        _P(2, "Bakso Keju"),
        _P(3, "Sosis Bakar"),
    ]
    scores = compute_similarity_scores(products)
    # All three products have completely unique words (no shared words)
    assert scores[1] == 0  # 'telur', 'asin' both unique
    assert scores[2] == 0  # 'bakso', 'keju' both unique
    assert scores[3] == 0  # 'sosis', 'bakar' both unique


def test_similarity_score_with_shared_word():
    """Products sharing a word should both get score > 0."""
    products = [
        _P(1, "Telur Asin"),
        _P(2, "Bakso Keju"),
        _P(3, "Bakso Sapi"),  # shares 'bakso' with #2
    ]
    scores = compute_similarity_scores(products)
    assert scores[1] == 0  # 'telur', 'asin' both unique
    assert scores[2] == 1  # 'bakso' shared with #3
    assert scores[3] == 1  # 'bakso' shared with #2


def test_similarity_score_multi_word_match():
    """Product with 2 shared words → score = sum of other-product counts."""
    products = [
        _P(1, "Bakso Sapi"),
        _P(2, "Bakso Ikan"),
        _P(3, "Bakso Keju"),
    ]
    scores = compute_similarity_scores(products)
    # Each product: 'bakso' shared with 2 others → +2; unique word → +0
    assert scores[1] == 2
    assert scores[2] == 2
    assert scores[3] == 2


def test_similarity_score_higher_for_more_shared():
    """Product with high-frequency word should rank above low-frequency word."""
    products = [
        _P(1, "Kerupuk Bawang"),
        _P(2, "Kerupuk Oren"),
        _P(3, "Kerupuk Bintang"),
        _P(4, "Kerupuk Uyel"),
        _P(5, "Kerupuk Tomat"),
        _P(6, "Telur"),
    ]
    scores = compute_similarity_scores(products)
    for i in range(1, 6):
        assert scores[i] == 4, f"Product {i} should score 4"
    assert scores[6] == 0


def test_build_sql_basic():
    """CASE WHEN SQL should match expected format."""
    sql = build_similarity_order_sql([42, 18, 7])
    assert sql == "CASE id WHEN 42 THEN 0 WHEN 18 THEN 1 WHEN 7 THEN 2 ELSE 1000000 END, name"


def test_build_sql_empty_returns_none():
    assert build_similarity_order_sql([]) is None


def test_build_sql_caps_at_1000():
    """Long lists should be capped to avoid SQL parsing overhead."""
    ids = list(range(1, 2001))
    sql = build_similarity_order_sql(ids)
    when_count = sql.count('WHEN ')
    assert when_count == 1000, f"Expected 1000 WHENs, got {when_count}"


def test_end_to_end_sorting():
    """End-to-end: full sort pipeline produces expected order."""
    products = [
        _P(1, "Kerupuk Bawang"),
        _P(2, "Kerupuk Oren"),
        _P(3, "Kerupuk Bintang"),
        _P(4, "Bakso Sapi"),
        _P(5, "Bakso Ikan"),
        _P(6, "Telur Asin"),
        _P(7, "Sosis"),
    ]
    # 'kerupuk' in 3 products, 'bakso' in 2 products
    scores = compute_similarity_scores(products)
    name_lower = {p.id: p.name.lower() for p in products}
    sorted_ids = sorted(
        [p.id for p in products],
        key=lambda pid: (-scores[pid], name_lower[pid])
    )
    # Expected: kerupuk products first (score 2, alphabetical),
    # then bakso products (score 1, alphabetical),
    # then score-0 alphabetical: "sosis" < "telur asin"
    # Kerupuk: "bawang" < "bintang" < "oren" → 1, 3, 2
    # Bakso: "ikan" < "sapi" → 5, 4
    assert sorted_ids == [1, 3, 2, 5, 4, 7, 6], f"Got: {sorted_ids}"


def test_extra_stopwords_filters_category_name():
    """When browsing /shop?category=seblak, 'seblak' should not inflate scores."""
    products = [
        _P(1, "Seblak Komplit"),
        _P(2, "Seblak Pentol"),
        _P(3, "Kerupuk Bawang"),
        _P(4, "Bakso"),
    ]
    # Without extra stopwords: 'seblak' shared by #1 and #2 → both score 1
    scores_no_stop = compute_similarity_scores(products)
    assert scores_no_stop[1] == 1
    assert scores_no_stop[2] == 1
    assert scores_no_stop[3] == 0
    assert scores_no_stop[4] == 0

    # With 'seblak' as extra stopword:
    scores_with_stop = compute_similarity_scores(
        products, extra_stopwords=frozenset({'seblak'})
    )
    assert scores_with_stop[1] == 0
    assert scores_with_stop[2] == 0
    assert scores_with_stop[3] == 0
    assert scores_with_stop[4] == 0


def run_all():
    """Run all tests without pytest."""
    tests = [
        ('test_tokenize_basic', test_tokenize_basic),
        ('test_tokenize_strips_punctuation_and_digits', test_tokenize_strips_punctuation_and_digits),
        ('test_tokenize_filters_stopwords', test_tokenize_filters_stopwords),
        ('test_tokenize_filters_short_words', test_tokenize_filters_short_words),
        ('test_tokenize_dedupes_within_product', test_tokenize_dedupes_within_product),
        ('test_tokenize_empty', test_tokenize_empty),
        ('test_tokenize_case_insensitive', test_tokenize_case_insensitive),
        ('test_tokenize_unicode', test_tokenize_unicode),
        ('test_tokenize_extra_stopwords', test_tokenize_extra_stopwords),
        ('test_similarity_score_zero_for_unique_words', test_similarity_score_zero_for_unique_words),
        ('test_similarity_score_with_shared_word', test_similarity_score_with_shared_word),
        ('test_similarity_score_multi_word_match', test_similarity_score_multi_word_match),
        ('test_similarity_score_higher_for_more_shared', test_similarity_score_higher_for_more_shared),
        ('test_build_sql_basic', test_build_sql_basic),
        ('test_build_sql_empty_returns_none', test_build_sql_empty_returns_none),
        ('test_build_sql_caps_at_1000', test_build_sql_caps_at_1000),
        ('test_end_to_end_sorting', test_end_to_end_sorting),
        ('test_extra_stopwords_filters_category_name', test_extra_stopwords_filters_category_name),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed, total {passed + failed}")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(run_all())
