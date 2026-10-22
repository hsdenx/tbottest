"""
Unit tests for scripts/registermap/am335x_create_registermap.py, with an
outline and pages of text as pdfplumber gives them for the AM335x
Technical Reference Manual: module and register entries, the memory map
tables of chapter 2, field tables over a page break, page headers and
footers.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import load_module

HERE = os.path.dirname(__file__)
SCRIPTS = os.path.join(HERE, "..", "scripts", "registermap")
am = load_module("am335x_create_registermap", os.path.join(SCRIPTS, "am335x_create_registermap.py"))
REGDUMP = os.path.join(SCRIPTS, "regdump.py")

SP = " "
OUTLINE = [
    (1, f"2{SP}Memory Map", 10),
    (2, f"19.5{SP}UART Registers", 100),
    (3, f"19.5.1{SP}UART Registers", 100),
    (4, f"19.5.1.1{SP}THR Register (offset = 0h) [reset = 0h]", 100),
    (4, f"19.5.1.2{SP}LCR Register (offset = Ch) [reset = 0h]", 101),
    (3, f"25.4.1{SP}GPIO Registers", 200),
    (4, f"25.4.1.16{SP}GPIO_OE Register (offset = 134h) [reset = FFFFFFFFh]", 200),
    (4, f"25.4.1.17{SP}GPIO_DATAIN Register (offset = 138h) [reset = 0h]", 202),
    (4, f"25.4.1.18{SP}Something else", 203),
]

MAPLINES = [
    "Table 2-2. L4_WKUP Peripheral Memory Map",
    "Region Name Start Address (hex) End Address (hex) Size Description",
    "CM_PER 0x44E0_0000 0x44E0_3FFF 1KB Clock Module Peripheral Registers",
    "CM_WKUP 0x44E0_0400 0x44E0_04FF 256 Bytes Clock Module Wakeup Registers",
    "0x44E0_6000 0x44E0_6FFF 4KB Reserved",
    "Reserved 0x44E0_3000 0x44E0_3FFF 4KB Reserved",
    "GPIO0 0x44E0_7000 0x44E0_7FFF 4KB GPIO Registers",
    "UART0 0x44E0_9000 0x44E0_9FFF 4KB UART Registers",
    "Table 2-3. L4_PER Peripheral Memory Map",
    "UART1 0x4802_2000 0x4802_2FFF 4KB UART1 Registers",
    "Mailbox 0 0x480C_8000 0x480C_8FFF 4KB Mailbox Registers",
    "Table 2-4. L4 Fast Peripheral Memory Map (continued)",
    "PRU_ICSS 0x4A30_0000 0x4A37_FFFF 512KB PRU-ICSS",
]

PAGES = {
    100: [
        "UART Registers www.ti.com",
        "19.5.1.1 THR Register (offset = 0h) [reset = 0h]",
        "Figure 19-34. THR Register",
        "Table 19-30. THR Register Field Descriptions",
        "Bit Field Type Reset Description",
        "15-8 RESERVED R 0h",
        "7-0 THR W 0h Transmit holding register.",
        "Value 0 to FFh.",
        "4268 Universal Asynchronous Receiver/Transmitter (UART) SPRUH73L-October 2011",
        "Submit Documentation Feedback",
    ],
    101: [
        "www.ti.com UART Registers",
        "19.5.1.2 LCR Register (offset = Ch) [reset = 0h]",
        "Table 19-31. LCR Register Field Descriptions",
        "Bit Field Type Reset Description",
        "7 DIV_EN R/W 0h Divisor latch enable.",
        "0h = Normal operating condition.",
        "19.5.1.3 MCR Register (offset = 10h) [reset = 0h]",
    ],
    200: [
        "25.4.1.16 GPIO_OE Register (offset = 134h) [reset = FFFFFFFFh]",
        "Table 25-21. GPIO_OE Register Field Descriptions",
        "Bit Field Type Reset Description",
        "31-0 OUTPUTEN[n] R/W FFFFFFFFh Output Data Enable",
        "0h = The corresponding GPIO port is configured as an output.",
        "SPRUH73L-October 2011-Revised February 2015 General-Purpose Input/Output 4893",
        "Copyright 2011-2015, Texas Instruments Incorporated",
    ],
    201: [
        "Registers www.ti.com",
        "Table 25-21. GPIO_OE Register Field Descriptions (continued)",
        "Bit Field Type Reset Description",
        "1h = The corresponding GPIO port is configured as an input.",
        "Figure 25-23. GPIO_DATAIN Register",
    ],
    202: [
        "Table 25-22. GPIO_DATAIN Register Field Descriptions",
        "Bit Field Type Reset Description",
        "31-16 TxRqs_32:17_ R 0h Transmission request bits",
        "15-0 CPSW_3G_IDENT R-0 0 Identification",
        "Table 25-23. Next table",
    ],
}


def page_lines(page):
    return PAGES.get(page, [])


class TestOutline:
    def test_modules_and_registers(self):
        modules, registers = am.outline_registers(OUTLINE)
        assert [(m["name"], m["chapter"]) for m in modules] == [
            ("UART", "19.5"),
            ("UART", "19.5.1"),
            ("GPIO", "25.4.1"),
        ]
        assert [(r["name"], r["offset"], r["reset"], r["page"], r["module"]) for r in registers] == [
            ("THR", 0x0, "0", 100, "UART"),
            ("LCR", 0xC, "0", 101, "UART"),
            ("GPIO_OE", 0x134, "FFFFFFFF", 200, "GPIO"),
            ("GPIO_DATAIN", 0x138, "0", 202, "GPIO"),
        ]
        # the innermost module section
        assert registers[0]["chapter"] == "19.5.1.1"


class TestMemoryMap:
    def test_rows(self):
        rows = am.memory_map(MAPLINES)
        assert [(r["name"], r["bus"]) for r in rows] == [
            ("CM_PER", "L4_WKUP"),
            ("CM_WKUP", "L4_WKUP"),
            ("GPIO0", "L4_WKUP"),
            ("UART0", "L4_WKUP"),
            ("UART1", "L4_PER"),
            ("Mailbox 0", "L4_PER"),
            ("PRU_ICSS", "L4_FAST"),
        ]

    def test_end_and_size_disagree(self):
        cm_per = am.memory_map(MAPLINES)[0]
        # 0x44E0_3FFF in the table, but 1KB, and CM_WKUP follows at 0x44E0_0400
        assert (cm_per["start"], cm_per["end"]) == (0x44E00000, 0x44E003FF)

    @pytest.mark.parametrize(
        "size,expected",
        [("4KB", 4096), ("256 Bytes", 256), ("1MB", 1 << 20), ("1GB", 1 << 30), ("x", None)],
    )
    def test_size_bytes(self, size, expected):
        assert am.size_bytes(size) == expected


@pytest.mark.parametrize(
    "name,module",
    [
        ("UART1", "UART"),
        ("McSPI0", "SPI"),
        ("DMTIMER1_1MS", "DMTIMER_1MS"),
        ("DMTIMER2", "TIMER"),
        ("MMCHS0", "MULTIMEDIA_CARD"),
        ("PRM_DEV", "PRM_DEVICE"),
        ("CM_PER", "CM_PER"),
        ("Control Module", "CONTROL_MODULE"),
        ("TPTC1 (EDMA3TC1)", "EDMA3TC"),
        ("GPMC", "GPMC"),
        ("PRU_ICSS", None),
        ("CM_NOSUCH", None),
    ],
)
def test_instance_module(name, module):
    modules = {
        "UART", "SPI", "DMTIMER_1MS", "TIMER", "MULTIMEDIA_CARD", "PRM_DEVICE",
        "CM_PER", "CONTROL_MODULE", "EDMA3TC", "GPMC",
    }
    assert am.instance_module(name, modules) == module


class TestFields:
    def test_table_without_header_footer(self):
        rows = am.field_lines(page_lines, 100, "THR")
        assert rows == ["15-8 RESERVED R 0h", "7-0 THR W 0h Transmit holding register.", "Value 0 to FFh."]

    def test_ends_at_heading(self):
        assert am.field_lines(page_lines, 101, "LCR") == [
            "7 DIV_EN R/W 0h Divisor latch enable.",
            "0h = Normal operating condition.",
        ]

    def test_over_a_page_break(self):
        fields = am.parse_fields(am.field_lines(page_lines, 200, "GPIO_OE"))
        assert fields == [
            {
                "range": "31-0",
                "field": "OUTPUTEN",
                "description": "Output Data Enable\n"
                "0h = The corresponding GPIO port is configured as an output.\n"
                "1h = The corresponding GPIO port is configured as an input.\n",
            }
        ]

    def test_special_names_and_types(self):
        fields = am.parse_fields(am.field_lines(page_lines, 202, "GPIO_DATAIN"))
        assert [(f["range"], f["field"]) for f in fields] == [
            ("31-16", "TxRqs_32:17_"),
            ("15-0", "CPSW_3G_IDENT"),
        ]

    def test_reserved_gets_a_text(self):
        fields = am.parse_fields(["15-8 RESERVED R 0h", "31-18 Reserved R 0h"])
        assert [f["description"] for f in fields] == ["Reserved\n", "Reserved\n"]

    def test_no_table(self):
        assert am.field_lines(page_lines, 100, "NOSUCH") == []


def test_build_registermap():
    modules, registers = am.outline_registers(OUTLINE)
    regmap = am.build_registermap(modules, registers, am.memory_map(MAPLINES), page_lines)
    permaps = {p["peripheral"]: p for p in regmap[0]["peripheralmaps"]}
    # instances of a module the outline has, the others are left out
    assert sorted(permaps) == ["GPIO0", "UART0", "UART1"]
    assert permaps["UART1"] == {
        "bus": "L4_PER",
        "range": "0x48022000 - 0x48022FFF",
        "size": "4KB",
        "peripheral": "UART1",
        "peripheralmap": "UART registers",
    }
    maps = {m["mapname"]: m for m in regmap[1]["registermaps"]}
    assert sorted(maps) == ["GPIO registers", "UART registers"]
    oe = maps["GPIO registers"]["registers"][0]
    assert (oe["registername"], oe["offset"], oe["resetvalue"], oe["page"], oe["chapter"]) == (
        "GPIO_OE", "0x134", "0xFFFFFFFF", 200, "25.4.1.16",
    )


def test_registermap_with_regdump(tmp_path):
    """the registermap works with regdump.py and registermap.py"""
    modules, registers = am.outline_registers(OUTLINE)
    regmap = am.build_registermap(modules, registers, am.memory_map(MAPLINES), page_lines)
    (tmp_path / "am335x_registers.json").write_text(json.dumps(regmap))
    env = dict(os.environ, PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    res = subprocess.run(
        [sys.executable, REGDUMP, "-s", "am335x", "-i", str(tmp_path), "-o", str(tmp_path),
         '[{"address":"0x4802200C","value":"0x83"}]'],
        capture_output=True, text=True, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    dump = (tmp_path / "am335x_result.txt").read_text()
    assert "register name: LCR addr 0x4802200C val: 0x83 RM page 101" in dump
    assert "7      DIV_EN                         val 1" in dump
