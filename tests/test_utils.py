"""
Unit tests for tbottest/common/utils.py's string_to_dict(). Pure
string parsing, no tbot dependency. Used by tc/process.py's
ps/top output parsers.
"""

import os

import pytest

from conftest import load_module

utils = load_module(
    "tbottest_common_utils",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "common", "utils.py"),
)

string_to_dict = utils.string_to_dict


class TestStringToDict:
    def test_docstring_example(self):
        result = string_to_dict(
            "hello, my name is dan and I am a 33 year old developer",
            "hello, my name is {name} and I am a {age} year old {what}",
        )
        assert result == {"name": "dan", "age": "33", "what": "developer"}

    def test_ps_style_line(self):
        result = string_to_dict(
            "172 172 0.0 0 20 rngd",
            r"{PID}\s+{TID}\s+{CPU}\s+{NI}\s+{PRI}\s+{CMD}",
        )
        assert result == {
            "PID": "172",
            "TID": "172",
            "CPU": "0.0",
            "NI": "0",
            "PRI": "20",
            "CMD": "rngd",
        }

    def test_no_match_raises(self):
        # search() looks anywhere in the string, so a single word can
        # never match a "{a}\s+{b}" (two whitespace-separated tokens)
        # pattern
        with pytest.raises(AssertionError):
            string_to_dict("oneword", "{PID}\\s+{TID}")

    def test_values_never_contain_spaces(self):
        # regex is built with [^\s]+ per placeholder, so a value can
        # never itself contain whitespace
        result = string_to_dict("a=1 b=2", "{first}={x} {second}={y}")
        assert result == {"first": "a", "x": "1", "second": "b", "y": "2"}
