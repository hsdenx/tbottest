"""
Unit tests for scripts/registermap/mpc855_create_registermap.py, with
lines as pdfplumber gives them for the MPC855T user's manual: Table 2-1
with its blocks, a line of the table of contents, field tables with bit
lists, lines of values and the bit numbering from the most significant
bit.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import load_module

HERE = os.path.dirname(__file__)
SCRIPTS = os.path.join(HERE, "..", "scripts", "registermap")
mpc = load_module("mpc855_create_registermap", os.path.join(SCRIPTS, "mpc855_create_registermap.py"))
REGDUMP = os.path.join(SCRIPTS, "regdump.py")

# (page, line) as content_lines() gives them
LINES = [
    (8, "10.4.2 SIU Module Configuration Register (SIUMCR) 10-5"),
    (95, "Table 2-1. MPC855T Internal Memory Map"),
    (95, "Offset Name Size Section/Page"),
    (95, "General System Interface Unit"),
    (95, "000 SIUMCR—SIU module configuration register 32 bits 10.4.2/-5"),
    (95, "008–00D Reserved 6 bytes —"),
    (95, "00E SWSR—Software service register 16 bits 10.7.1/-21"),
    (95, "Memory Controller"),
    (96, "100 BR0—Base register bank 0 32 bits 15.4.1/-9"),
    (96, "0E0 PGCRA—PCMCIA interface general control 32 bits 16.4.4/-13"),
    (96, "register A"),
    (96, "Input/Output Port"),
    (96, "950 PADIR—Port A data direction register 16 bits 33.2.1.3/-6"),
    (96, "952 PAPAR—Port A pin assignment register 16 bits 33.2.1.4/-7"),
    (97, "Table 2-2. Something else"),
    (275, "10.4.2 SIU Module Configuration Register (SIUMCR)"),
    (275, "Table 10-3. SIUMCR Field Descriptions"),
    (275, "Bits Name Description"),
    (275, "0 EARB External arbitration."),
    (275, "0 Internal arbitration is performed."),
    (275, "1 External arbitration is assumed."),
    (276, "1–3 EARP External arbitration request priority."),
    (276, "4–7 — Reserved, should be cleared."),
    (276, "Table 10-4. Next"),
    (435, "15.4.1 Base Registers (BR0–BR7)"),
    (435, "Table 15-3. BRx Field Descriptions"),
    (435, "Bits Name Description"),
    (435, "0–16 BA Base address."),
    (435, "31 V Valid bit."),
    (435, "15.4.2 Option Registers (OR0–OR7)"),
    (898, "33.2.1.3 Port A Data Direction Register (PADIR)"),
    (898, "Figure 33-3. Port A Data Direction Register (PADIR)"),
    (898, "Table 33-4. PADIR Bit Descriptions"),
    (898, "Bits Name Description"),
    (898, "0–15 DRn Port A data direction."),
    (898, "0 The corresponding signal is an input."),
    (898, "33.2.1.4 Port A Pin Assignment Register (PAPAR)"),
    (899, "Bit 0 1 2 3 4 5 6 7"),
    (899, "33.2.1.5 Next section"),
]
TEXT = [s for _p, s in LINES]


class TestMemoryMap:
    def test_rows_and_blocks(self):
        rows = mpc.memory_map(TEXT)
        assert [(r["offset"], r["name"], r["size"], r["section"], r["block"]) for r in rows] == [
            (0x000, "SIUMCR", 32, "10.4.2", "General System Interface Unit"),
            (0x00E, "SWSR", 16, "10.7.1", "General System Interface Unit"),
            (0x100, "BR0", 32, "15.4.1", "Memory Controller"),
            (0x0E0, "PGCRA", 32, "16.4.4", "Memory Controller"),
            (0x950, "PADIR", 16, "33.2.1.3", "Input/Output Port"),
            (0x952, "PAPAR", 16, "33.2.1.4", "Input/Output Port"),
        ]


@pytest.mark.parametrize(
    "bits,ranges",
    [("0", [(0, None)]), ("0–15", [(0, 15)]), ("8–12, 14", [(8, 12), (14, None)]),
     ("0–7, 13, 15", [(0, 7), (13, None), (15, None)])],
)
def test_bit_ranges(bits, ranges):
    assert mpc.bit_ranges(bits) == ranges


@pytest.mark.parametrize(
    "first,last,expected",
    [(0, None, "31"), (0, 15, "31-16"), (16, 31, "15-0"), (0, 16, "31-15"), (31, None, "0")],
)
def test_lsb_range(first, last, expected):
    assert mpc.lsb_range(first, last) == expected


class TestFields:
    def test_values_are_no_fields(self):
        fields = mpc.parse_fields(mpc.field_rows(TEXT[15:], "10.4.2"))
        assert [(f["range"], f["field"]) for f in fields] == [
            ("31", "EARB"),
            ("30-28", "EARP"),
            ("27-24", "Reserved"),
        ]
        assert fields[0]["description"] == (
            "External arbitration.\n0 Internal arbitration is performed.\n"
            "1 External arbitration is assumed.\n"
        )
        assert fields[2]["description"] == "Reserved, should be cleared.\n"

    def test_bit_descriptions_and_index_letter(self):
        fields = mpc.parse_fields(mpc.field_rows(TEXT[30:], "33.2.1.3"))
        assert [(f["range"], f["field"]) for f in fields] == [("31-16", "DRn")]

    def test_bit_list(self):
        fields = mpc.parse_fields(["8–12, 14 ODn Open drain.", "0 Actively driven."])
        assert [(f["range"], f["field"]) for f in fields] == [("23-19", "ODn"), ("17", "ODn")]
        assert fields[1]["description"] == "Open drain.\n0 Actively driven.\n"

    def test_section_without_table(self):
        assert mpc.field_rows(TEXT[36:], "33.2.1.4") == []


def test_content_lines():
    pages = {
        1: ["Programming the SIU", "10.4.2 SIU Module (SIUMCR)", "text", "Chapter 10. System Interface Unit"],
        2: ["Running header", "more text", "MPC855T User's Manual", "10-6"],
    }
    lines = mpc.content_lines(lambda p: pages[p], 2)
    assert lines == [(1, "10.4.2 SIU Module (SIUMCR)"), (1, "text"), (2, "more text")]


class TestBuildRegistermap:
    @pytest.fixture
    def regmap(self):
        return mpc.build_registermap(LINES)

    def test_relative_to_immr(self, regmap):
        assert regmap[0]["relative_to"] == "IMMR"
        permaps = {p["peripheral"]: p["range"] for p in regmap[0]["peripheralmaps"]}
        assert permaps["General System Interface Unit"] == "0x00000000 - 0x000000DF"

    def test_section_after_the_table_of_contents(self, regmap):
        gsiu = regmap[1]["registermaps"][0]
        siumcr = gsiu["registers"][0]
        assert (siumcr["registername"], siumcr["page"], siumcr["chapter"]) == ("SIUMCR", 275, "10.4.2")
        assert siumcr["size"] == 32 and siumcr["resetvalue"] is None
        assert [b["field"] for b in siumcr["bits"]] == ["EARB", "EARP", "Reserved"]

    def test_offsets_in_the_block(self, regmap):
        maps = {m["mapname"]: m for m in regmap[1]["registermaps"]}
        port = maps["Input/Output Port registers"]["registers"]
        assert [(r["registername"], r["offset"], r["size"]) for r in port] == [
            ("PADIR", "0x0", 16),
            ("PAPAR", "0x2", 16),
        ]

    def test_with_regdump(self, regmap, tmp_path):
        (tmp_path / "mpc855_registers.json").write_text(json.dumps(regmap))
        env = dict(os.environ, PYTHONNOUSERSITE="1")
        env.pop("PYTHONPATH", None)
        res = subprocess.run(
            [sys.executable, REGDUMP, "-s", "mpc855", "-i", str(tmp_path), "-o", str(tmp_path),
             "--base", "0xFFF00000", '[{"address":"0xFFF00000","value":"0x80000000"}]'],
            capture_output=True, text=True, env=env,
        )
        assert res.returncode == 0, res.stdout + res.stderr
        dump = (tmp_path / "mpc855_result.txt").read_text()
        assert "register name: SIUMCR addr 0xFFF00000 val: 0x80000000 RM page 275" in dump
        # bit 0 of the manual, the most significant bit
        assert "31     EARB                           val 1" in dump
