"""
Unit tests for scripts/registermap/stm32_svd_create_registermap.py, with
a small SVD file in the form of the ones of ST: a peripheral with its
registers, one derived from it, the three ways of an SVD to give the bits
of a field, and an old registermap of the reference manual that names the
registers otherwise.
"""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from conftest import load_module

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "registermap", "stm32_svd_create_registermap.py")
REGDUMP = os.path.join(HERE, "..", "scripts", "registermap", "regdump.py")
# the script imports stm32_rm_descriptions from its own directory
sys.path.insert(0, os.path.dirname(SCRIPT))
svd = load_module("stm32_svd_create_registermap", SCRIPT)

SVD = """<?xml version="1.0" encoding="utf-8"?>
<device>
  <name>STM32TEST</name>
  <peripherals>
    <peripheral>
      <name>USART1</name>
      <groupName>USART</groupName>
      <baseAddress>0x5C000000</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x400</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>CR1</name>
          <addressOffset>0x0</addressOffset>
          <resetValue>0x00000000</resetValue>
          <fields>
            <field><name>UE</name><description>UE</description>
              <bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
            <field><name>M</name><description>Word
              length</description><lsb>12</lsb><msb>13</msb></field>
            <field><name>DEAT</name><description>DEAT</description>
              <bitRange>[25:21]</bitRange></field>
          </fields>
        </register>
        <register>
          <name>BRR</name>
          <addressOffset>0xC</addressOffset>
          <size>0x10</size>
          <resetValue>0x0000</resetValue>
          <fields>
            <field><name>BRR</name><description>BRR</description>
              <bitOffset>0</bitOffset><bitWidth>16</bitWidth></field>
          </fields>
        </register>
      </registers>
    </peripheral>
    <peripheral derivedFrom="USART1">
      <name>USART6</name>
      <baseAddress>0x44003000</baseAddress>
    </peripheral>
  </peripherals>
</device>
"""

# an old registermap of the reference manual, other register names, one
# field of another name
OLD = [
    {
        "peripheralmaps": [
            {
                "bus": "APB5",
                "range": "0x5C000000 - 0x5C0003FF",
                "size": "1KB",
                "peripheral": "USART1",
                "peripheralmap": "USART registers",
            },
            {
                "bus": "APB2",
                "range": "0x44003000 - 0x440033FF",
                "size": "1KB",
                "peripheral": "USART6",
                "peripheralmap": "USART registers",
            },
            {
                "bus": "APB1",
                "range": "0x40011000 - 0x400113FF",
                "size": "1KB",
                "peripheral": "UART5",
                "peripheralmap": "USART registers",
            },
        ]
    },
    {
        "registermaps": [
            {
                "mapname": "USART registers",
                "registers": [
                    {
                        "registername": "USART_CR1",
                        "offset": "0x00",
                        "page": 2626,
                        "chapter": "53.8.1",
                        "resetvalue": "0x0000",
                        "bits": [
                            {"range": "0", "field": "UE", "description": "USART enable\n"},
                            {"range": "13:12", "field": "M1M0", "description": "Word length\n"},
                        ],
                    },
                    {
                        "registername": "USART_CR1-alternate",
                        "offset": "0x00",
                        "page": 2630,
                        "chapter": "53.8.2",
                        "resetvalue": "0x0000",
                        "bits": [{"range": "0", "field": "UE", "description": "other view\n"}],
                    },
                ],
            }
        ]
    },
]


@pytest.fixture
def root():
    return ET.fromstring(SVD)


def regmap(registermap, name):
    return next(m for m in registermap[1]["registermaps"] if m["mapname"] == name)


class TestSvdToRegistermap:
    def test_peripheralmaps(self, root):
        permaps = svd.svd_to_registermap(root)[0]["peripheralmaps"]
        assert permaps == [
            {
                "bus": None,
                "range": "0x5C000000 - 0x5C0003FF",
                "size": "1KB",
                "peripheral": "USART1",
                "peripheralmap": "USART1 registers",
            },
            {
                "bus": None,
                "range": "0x44003000 - 0x440033FF",
                "size": "1KB",
                "peripheral": "USART6",
                "peripheralmap": "USART1 registers",
            },
        ]

    def test_derived_peripheral_has_no_registermap(self, root):
        regmaps = svd.svd_to_registermap(root)[1]["registermaps"]
        assert [m["mapname"] for m in regmaps] == ["USART1 registers"]

    def test_registers(self, root):
        cr1, brr = regmap(svd.svd_to_registermap(root), "USART1 registers")["registers"]
        assert cr1["registername"] == "CR1"
        assert cr1["offset"] == "0x00"
        assert cr1["resetvalue"] == "0x00000000"
        assert cr1["page"] is None and cr1["chapter"] is None
        # highest bits first, the three ways of an SVD to give them
        assert [(b["range"], b["field"]) for b in cr1["bits"]] == [
            ("25:21", "DEAT"),
            ("13:12", "M"),
            ("0", "UE"),
        ]
        assert cr1["bits"][1]["description"] == "Word length\n"
        assert brr["offset"] == "0x0C"
        assert brr["bits"] == [{"range": "15:0", "field": "BRR", "description": "BRR\n"}]


@pytest.mark.parametrize(
    "size,expected", [(0x400, "1KB"), (0x2000, "8KB"), (0x100000, "1MB"), (0x100, "256B")]
)
def test_size_str(size, expected):
    assert svd.size_str(size) == expected


class TestMergeBus:
    def test_bus_by_base_address(self, root):
        new = svd.svd_to_registermap(root)
        assert svd.merge_bus(new, OLD) == 2
        assert [(p["peripheral"], p["bus"]) for p in new[0]["peripheralmaps"]] == [
            ("USART1", "APB5"),
            ("USART6", "APB2"),
        ]

    def test_part_of_a_block_and_unknown(self, root):
        new = svd.svd_to_registermap(root)
        new[0]["peripheralmaps"][0]["range"] = "0x5C000100 - 0x5C0001FF"
        new[0]["peripheralmaps"][1]["range"] = "0xE000E100 - 0xE000E500"
        assert svd.merge_bus(new, OLD) == 1
        assert [p["bus"] for p in new[0]["peripheralmaps"]] == ["APB5", None]


class TestMerge:
    def test_by_address_and_offset(self, root):
        new = svd.svd_to_registermap(root)
        assert svd.merge_descriptions(new, OLD) == (1, 2)
        cr1 = regmap(new, "USART1 registers")["registers"][0]
        assert (cr1["page"], cr1["chapter"]) == (2626, "53.8.1")
        texts = {b["field"]: b["description"] for b in cr1["bits"]}
        # UE by name, M by its bit range, DEAT stays as in the SVD
        assert texts == {"UE": "USART enable\n", "M": "Word length\n", "DEAT": "DEAT\n"}

    def test_register_without_old_one_stays(self, root):
        new = svd.svd_to_registermap(root)
        svd.merge_descriptions(new, OLD)
        brr = regmap(new, "USART1 registers")["registers"][1]
        assert brr["page"] is None

    def test_one_pair_per_maps(self, root):
        pairs = svd.map_pairs(svd.svd_to_registermap(root), OLD)
        assert [(o["mapname"], n["mapname"]) for o, n in pairs] == [
            ("USART registers", "USART1 registers")
        ]


def test_clean_description():
    desc = "USART enable\n1: enabled\n2628/4054 RM0436 Rev 7\nmore 2629/4054 RM0436 Rev\n"
    assert svd.clean_description(desc) == "USART enable\n1: enabled\nmore\n"


def test_map_groups(root):
    assert svd.map_groups(root) == {"USART1 registers": ("USART", "USART1")}


def test_script_and_regdump(tmp_path):
    """the written registermap works with regdump.py (and registermap.py)"""
    (tmp_path / "test.svd").write_text(SVD)
    (tmp_path / "old.json").write_text(json.dumps(OLD))
    out = tmp_path / "stm32mp157_registers.json"
    res = subprocess.run(
        [sys.executable, SCRIPT, "-s", str(tmp_path / "test.svd"),
         "-m", str(tmp_path / "old.json"), "-o", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert "took over 1 registers and 2 field descriptions" in res.stdout
    assert "took over the bus of 2 peripherals" in res.stdout
    assert "2 peripherals, 1 registermaps, 2 registers" in res.stdout
    env = dict(os.environ, PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    res = subprocess.run(
        [sys.executable, REGDUMP, "-s", "stm32mp157", "-i", str(tmp_path), "-o", str(tmp_path),
         '[{"address":"0x44003000","value":"0x00003001"}]'],
        capture_output=True, text=True, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    dump = (tmp_path / "stm32mp157_result.txt").read_text()
    assert "register name: CR1 addr 0x44003000 val: 0x00003001 RM page 2626" in dump
    assert "13:12  M                              val 11" in dump
