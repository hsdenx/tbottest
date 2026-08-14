"""
Unit tests for the pure-logic helpers in tbottest/tc/common.py.
"""

import os

import pytest

from conftest import install_fake_initconfig, load_module

install_fake_initconfig()

common = load_module(
    "tbottest_tc_common",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common.py"),
)


LOG = (
    "line one\n"
    "line two contains FOO\n"
    "line three contains BAR\n"
    "line four\n"
)


class TestSearchStringInMultiline:
    def test_found(self):
        assert common.search_string_in_multiline("FOO", LOG) is True

    def test_not_found(self):
        assert common.search_string_in_multiline("NOPE", LOG) is False

    def test_substring_match(self):
        # "contains" appears on two separate lines
        assert common.search_string_in_multiline("contains", LOG) is True

    def test_empty_lines(self):
        assert common.search_string_in_multiline("anything", "") is False


class TestSearchMultistringInMultiline:
    def test_all_found(self):
        assert common.search_multistring_in_multiline(["FOO", "BAR"], LOG) is True

    def test_one_missing(self):
        assert common.search_multistring_in_multiline(["FOO", "NOPE"], LOG) is False

    def test_none_found(self):
        assert common.search_multistring_in_multiline(["NOPE1", "NOPE2"], LOG) is False

    def test_empty_searches_list(self):
        # vacuously true, like all([])
        assert common.search_multistring_in_multiline([], LOG) is True

    def test_single_search(self):
        assert common.search_multistring_in_multiline(["line four"], LOG) is True


class TestPollUntil:
    def test_succeeds_immediately(self):
        calls = []

        def check():
            calls.append(1)
            return True

        assert common._poll_until(check, loops=5, timeout=0, errmsg="nope") is True
        assert len(calls) == 1

    def test_succeeds_after_retries(self):
        results = iter([False, False, True])

        def check():
            return next(results)

        assert common._poll_until(check, loops=5, timeout=0, errmsg="nope") is True

    def test_raises_after_exhausting_loops(self):
        calls = []

        def check():
            calls.append(1)
            return False

        with pytest.raises(RuntimeError, match="device not found"):
            common._poll_until(check, loops=3, timeout=0, errmsg="device not found")

        # must have tried exactly `loops` times, no more, no less
        assert len(calls) == 3

    def test_zero_loops_raises_immediately_without_calling_check(self):
        calls = []

        def check():
            calls.append(1)
            return True

        with pytest.raises(RuntimeError):
            common._poll_until(check, loops=0, timeout=0, errmsg="nope")
        assert calls == []
