"""
Unit tests for tbottest/tc/registermap.py's REGISTERMAP class: the
NXP (flat list, direct address or address_cyclic) and STM32MP157
(peripheralmaps + registermaps) search/parse logic, all driven from
real (temp-file) JSON registermaps matching the formats documented in
registermap.py's own class docstring.
"""

import json
import os

import pytest

from conftest import install_real_submodule, load_module

install_real_submodule(
    "tbottest.tc.common_generic",
    os.path.join(
        os.path.dirname(__file__), "..", "tbottest", "tc", "common_generic.py"
    ),
)

registermap = load_module(
    "tbottest_tc_registermap",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "registermap.py"),
)

REGISTERMAP = registermap.REGISTERMAP


NXP_MAP = [
    {
        "register": "IOMUXC_SW_MUX_CTL_PAD_ENET_TXC",
        "address": "0x30330070",
        "address_cyclic": None,
        "page": 1438,
        "bits": [{"range": "31-5", "field": "-", "description": "reserved"}],
    },
    {
        "register": "GPIO_DR",
        "address": None,
        "address_cyclic": {
            "base": "0x30200000",
            "offset": "0x0",
            "step": 0x10000,
            "start": 0,
            "end": 2,
        },
        "page": 42,
        "bits": [],
    },
]

STM32_MAP = [
    {
        "peripheralmaps": [
            {
                "bus": "APB1",
                "range": "0x40005400 - 0x400057FF",
                "size": "1KB",
                "peripheral": "I2C1",
                "peripheralmap": "I2C_MAP",
            },
            {
                "bus": "APB1",
                "range": "0x40005800 - 0x40005BFF",
                "size": "1KB",
                "peripheral": "I2C2",
                "peripheralmap": "I2C_MAP",
            },
        ]
    },
    {
        "registermaps": [
            {
                "mapname": "I2C_MAP",
                "registers": [
                    {
                        "registername": "I2C_CR1",
                        "offset": "0x00",
                        "page": 100,
                        "bits": [{"range": "0", "field": "PE", "description": "enable"}],
                    },
                    {
                        "registername": "I2C_CR2",
                        "offset": "0x04",
                        "page": 101,
                        "bits": [],
                    },
                ],
            }
        ]
    },
]


@pytest.fixture
def nxp_map_path(tmp_path):
    p = tmp_path / "imx8mp_registers.json"
    p.write_text(json.dumps(NXP_MAP))
    return str(p)


@pytest.fixture
def stm32_map_path(tmp_path):
    p = tmp_path / "stm32mp157_registers.json"
    p.write_text(json.dumps(STM32_MAP))
    return str(p)


class TestInit:
    def test_socname_autodetected_from_filename(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path)
        assert rm.socname == "imx8mp"

    def test_socname_can_be_overridden(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path, socname="customsoc")
        assert rm.socname == "customsoc"

    def test_load_map_reads_json(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path)
        assert rm.registermap == NXP_MAP


class TestGetRegisternameFromDict:
    def test_imx8mp(self, nxp_map_path):
        assert REGISTERMAP(nxp_map_path).get_registername_from_dict() == "register"

    def test_stm32mp157(self, stm32_map_path):
        assert (
            REGISTERMAP(stm32_map_path).get_registername_from_dict() == "registername"
        )

    def test_unsupported_soc_raises(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path, socname="unsupported")
        with pytest.raises(RuntimeError, match="not found"):
            rm.get_registername_from_dict()


class TestNxpSearchAddress:
    def test_direct_address_match(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path)
        reg = rm.registermap_search_address("0x30330070")
        assert reg["register"] == "IOMUXC_SW_MUX_CTL_PAD_ENET_TXC"

    def test_address_not_found_returns_none(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path)
        assert rm.registermap_search_address("0xdeadbeef") is None

    def test_address_cyclic_match(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path)
        # base 0x30200000 + offset 0x0 + step 0x10000 * 1 = 0x30210000
        reg = rm.registermap_search_address("0x30210000")
        assert reg["register"] == "GPIO_DR"

    def test_address_cyclic_out_of_range_not_found(self, nxp_map_path):
        rm = REGISTERMAP(nxp_map_path)
        # step*3 would be instance 3, but end=2 -> only instances 0-2 valid
        reg = rm.registermap_search_address("0x30230000")
        assert reg is None


class TestStm32SearchAddress:
    def test_finds_register_by_address(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        # I2C1 base 0x40005400 + I2C_CR2 offset 0x04
        reg = rm.registermap_search_address("0x40005404")
        assert reg["registername"] == "I2C_CR2"

    def test_second_peripheral_instance(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        # I2C2 base 0x40005800 + I2C_CR1 offset 0x00
        reg = rm.registermap_search_address("0x40005800")
        assert reg["registername"] == "I2C_CR1"

    def test_address_outside_any_peripheral_raises(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        with pytest.raises(RuntimeError, match="No peripheral map found"):
            rm.registermap_search_address("0xffffffff")

    def test_address_in_peripheral_range_but_no_such_register_raises(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        with pytest.raises(RuntimeError, match="not found"):
            rm.registermap_search_address("0x400057FF")


class TestRegisternameToAddress:
    def test_first_instance(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        assert rm.registername_to_address("I2C_CR1", 0) == "0x40005400"

    def test_second_instance(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        assert rm.registername_to_address("I2C_CR2", 1) == "0x40005804"

    def test_unknown_register_raises(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        with pytest.raises(RuntimeError, match="Could not find register"):
            rm.registername_to_address("NO_SUCH_REG", 0)

    def test_unknown_instance_index_raises(self, stm32_map_path):
        rm = REGISTERMAP(stm32_map_path)
        with pytest.raises(RuntimeError, match="Could not find peripheralmap index"):
            rm.registername_to_address("I2C_CR1", 5)


class TestDumpRegisterFile:
    def test_writes_expected_content(self, stm32_map_path, tmp_path):
        rm = REGISTERMAP(stm32_map_path)
        out = tmp_path / "dump.txt"
        ok = rm.registermap_dump_register_file(str(out), "0x40005400", "0x00000001")
        assert ok is True
        content = out.read_text()
        assert "I2C_CR1" in content
        assert "0x40005400" in content
        # bit 0 (PE) of 0x00000001 is set
        assert "PE" in content
        assert "desc enable" in content

    def test_unknown_address_writes_not_found_and_returns_false(self, nxp_map_path, tmp_path):
        # unlike the STM32 search (which raises when nothing matches),
        # the NXP search returns None for an unmapped address, which
        # is the "not found" path registermap_dump_register_file()
        # actually handles
        rm = REGISTERMAP(nxp_map_path)
        out = tmp_path / "dump.txt"
        ok = rm.registermap_dump_register_file(str(out), "0xdeadbeef", "0x0")
        assert ok is False
        assert "not found" in out.read_text()
