"""CLI-level tests for primes.main (review round 1 fixes)."""

import pytest

import primes

PRIMES_BELOW_100 = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41,
    43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
]


def test_no_arguments_uses_default_limit(capsys):
    assert primes.main(["primes"]) == 0
    assert capsys.readouterr().out.strip() == str(PRIMES_BELOW_100)


def test_explicit_limit(capsys):
    assert primes.main(["primes", "50"]) == 0
    assert capsys.readouterr().out.strip() == str([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47])


def test_limit_two_via_cli_prints_empty_list(capsys):
    assert primes.main(["primes", "2"]) == 0
    assert capsys.readouterr().out.strip() == "[]"


def test_extra_arguments_are_a_usage_error(capsys):
    assert primes.main(["primes", "100", "200"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage" in captured.err.lower()


@pytest.mark.parametrize("bad", ["abc", "3.5", ""])
def test_non_integer_argument_is_a_usage_error(bad, capsys):
    assert primes.main(["primes", bad]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert bad in captured.err
    assert "traceback" not in captured.err.lower()
