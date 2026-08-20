import pytest

from primes import primes_below


def test_primes_below_100():
    assert primes_below(100) == [
        2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41,
        43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
    ]


def test_limit_is_exclusive():
    assert primes_below(31)[-1] == 29


def test_limit_two_returns_empty():
    assert primes_below(2) == []


def test_limit_one_returns_empty():
    assert primes_below(1) == []


def test_zero_and_negative_limits_return_empty():
    assert primes_below(0) == []
    assert primes_below(-10) == []


def test_smallest_prime():
    assert primes_below(3) == [2]


@pytest.mark.parametrize("bad", [3.5, "100", None, True])
def test_non_integer_limit_raises(bad):
    with pytest.raises(TypeError):
        primes_below(bad)


def test_all_results_are_prime_and_sorted():
    primes = primes_below(100)
    assert primes == sorted(primes)
    assert all(p >= 2 for p in primes)
    for p in primes:
        assert all(p % d for d in range(2, p))
