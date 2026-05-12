from server.routes.stats import _percentile_stats


def test_empty():
    assert _percentile_stats([]) is None


def test_single_value():
    r = _percentile_stats([42])
    assert r["median_seconds"] == 42
    assert r["p90_seconds"] == 42
    assert r["sample_size"] == 1


def test_n5():
    r = _percentile_stats([1, 2, 3, 4, 5])
    assert r["median_seconds"] == 3
    assert r["p90_seconds"] == 5


def test_n9():
    r = _percentile_stats(list(range(1, 10)))
    assert r["median_seconds"] == 5
    assert r["p90_seconds"] == 9


def test_n10_regression():
    """n=10 used to return max (10) as P90 due to int(0.9*10)==9 (last index)."""
    r = _percentile_stats(list(range(1, 11)))
    assert r["median_seconds"] == 5
    assert r["p90_seconds"] == 9


def test_n20():
    r = _percentile_stats(list(range(1, 21)))
    assert r["median_seconds"] == 10
    assert r["p90_seconds"] == 18


def test_unsorted_input():
    """Function must sort internally — caller should not need to pre-sort."""
    r = _percentile_stats([10, 1, 5, 3, 7])
    assert r["median_seconds"] == 5
    assert r["p90_seconds"] == 10
