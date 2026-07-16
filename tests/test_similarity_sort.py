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

# Extract only the algorithm section: from 'import re' to end of
# sort_product_ids_by_similarity function. We do this by finding the
# line numbers and slicing.
lines = src.split('\n')
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if line.startswith('import re') and start_idx is None:
        start_idx = i
    if 'def sort_product_ids_by_similarity' in line:
        # Find end of this function (next 'def' or 'class' at column 0)
        for j in range(i + 1, len(lines)):
            if lines[j].startswith('def ') or lines[j].startswith('class '):
                end_idx = j
                break
        break

if start_idx is None or end_idx is None:
    raise RuntimeError('Could not extract algorithm section')

algo_src = '\n'.join(lines[start_idx:end_idx])

# Strip any line that imports odoo
algo_src = '\n'.join(
    line for line in algo_src.split('\n')
    if not line.startswith('from odoo') and not line.startswith('import odoo')
)

ns = {}
exec(algo_src, ns)

tokenize = ns['tokenize']
compute_similarity_scores = ns['compute_similarity_scores']
sort_product_ids_by_similarity = ns['sort_product_ids_by_similarity']


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


def test_sort_returns_sorted_ids():
    """sort_product_ids_by_similarity returns list of IDs in similarity order."""
    products_data = [
        {'id': 1, 'name': "Kerupuk Bawang"},
        {'id': 2, 'name': "Kerupuk Oren"},
        {'id': 3, 'name': "Kerupuk Bintang"},
        {'id': 4, 'name': "Bakso Sapi"},
        {'id': 5, 'name': "Bakso Ikan"},
        {'id': 6, 'name': "Telur Asin"},
        {'id': 7, 'name': "Sosis"},
    ]
    sorted_ids = sort_product_ids_by_similarity(products_data)
    # Kerupuk (score 2) first, alphabetical: Bawang, Bintang, Oren → 1, 3, 2
    # Bakso (score 1) next, alphabetical: Ikan, Sapi → 5, 4
    # Score 0 alphabetical: "sosis" < "telur asin" → 7, 6
    assert sorted_ids == [1, 3, 2, 5, 4, 7, 6], f"Got: {sorted_ids}"


def test_sort_empty():
    """Empty input → empty list."""
    assert sort_product_ids_by_similarity([]) == []


def test_sort_single_product():
    """Single product → list with that ID."""
    result = sort_product_ids_by_similarity([{'id': 42, 'name': 'Solo'}])
    assert result == [42]


def test_sort_with_extra_stopwords():
    """Category name as stopword prevents it from inflating scores."""
    products_data = [
        {'id': 1, 'name': "Seblak Komplit"},
        {'id': 2, 'name': "Seblak Pentol"},
        {'id': 3, 'name': "Kerupuk Bawang"},
    ]
    # Without stopword: 'seblak' shared by #1 and #2 → both score 1
    sorted_no_stop = sort_product_ids_by_similarity(products_data)
    # Scores: 1=1, 2=1, 3=0. Sort: 1, 2 (score 1 alphabetical), then 3
    assert sorted_no_stop == [1, 2, 3], f"Without stopword: {sorted_no_stop}"

    # With 'seblak' stopword: 'seblak' filtered, scores all 0
    # → alphabetical: "Kerupuk Bawang" < "Seblak Komplit" < "Seblak Pentol"
    sorted_with_stop = sort_product_ids_by_similarity(
        products_data, extra_stopwords=frozenset({'seblak'})
    )
    assert sorted_with_stop == [3, 1, 2], f"With stopword: {sorted_with_stop}"


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
        ('test_sort_returns_sorted_ids', test_sort_returns_sorted_ids),
        ('test_sort_empty', test_sort_empty),
        ('test_sort_single_product', test_sort_single_product),
        ('test_sort_with_extra_stopwords', test_sort_with_extra_stopwords),
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
