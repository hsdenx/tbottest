"""
Unit tests for tbottest/tc/common_generic.py's get_bit_range().
Pure bit-manipulation logic, no tbot dependency at all.
"""

import os

import pytest

from conftest import load_module

common_generic = load_module(
    "tbottest_tc_common_generic",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common_generic.py"),
)

get_bit_range = common_generic.get_bit_range


class TestGetBitRange:
    def test_single_bit_set(self):
        # 0x1 -> bit 0 is 1
        assert get_bit_range("0x1", "0") == "1"

    def test_single_bit_clear(self):
        assert get_bit_range("0x0", "0") == "0"

    def test_dash_range(self):
        # 0x0F -> bits 3-0 = 1111
        assert get_bit_range("0xF", "3-0") == "1111"

    def test_colon_range(self):
        # same as dash, just ':' separator (as used by the STM32 registermap)
        assert get_bit_range("0xF", "3:0") == "1111"

    def test_range_order_independent(self):
        # "0-3" and "3-0" must give the same result
        assert get_bit_range("0xA", "0-3") == get_bit_range("0xA", "3-0")

    def test_extracts_middle_bits(self):
        # 0b101100 = 0x2C ; bits 4-2 = 011
        assert get_bit_range("0x2C", "4-2") == "011"

    def test_lsb_first_reverses_output(self):
        normal = get_bit_range("0xF", "3-0", lsb_first=False)
        reversed_ = get_bit_range("0xF", "3-0", lsb_first=True)
        assert reversed_ == normal[::-1]

    def test_leading_zeros_preserved(self):
        # bit 3 only set among bits 3-0 -> "1000", not "1"
        assert get_bit_range("0x8", "3-0") == "1000"

    def test_negative_bit_position_raises(self):
        # "-" is the range separator, so a genuine negative number can
        # only be expressed with the ":" separator
        with pytest.raises(ValueError):
            get_bit_range("0xF", "-1:3")

    def test_invalid_range_format_raises(self):
        with pytest.raises(ValueError):
            get_bit_range("0xF", "1-2-3")

    def test_whitespace_around_range_is_stripped(self):
        assert get_bit_range("0xF", " 3-0 ") == "1111"
