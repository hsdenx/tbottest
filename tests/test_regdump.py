"""
Unit tests for scripts/registermap/regdump.py.

regdump.py runs without tbot, so the tests start it as its own process
with the user site of Python switched off (PYTHONNOUSERSITE), in which no
tbot is installed, against small registermaps in the formats of
registermap.py: STM32MP157 (peripheralmaps and registermaps) and i.MX8MP
(a list of registers, with fixed and cyclic addresses).
"""

import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(__file__)
REGDUMP = os.path.join(HERE, "..", "scripts", "registermap", "regdump.py")

STM32MAP = [
    {
        "peripheralmaps": [
            {
                "bus": None,
                "range": "0x40012000 - 0x400123FF",
                "size": "1KB",
                "peripheral": "I2C1",
                "peripheralmap": "I2C1 registers",
            },
            {
                "bus": None,
                "range": "0x40013000 - 0x400133FF",
                "size": "1KB",
                "peripheral": "I2C2",
                "peripheralmap": "I2C1 registers",
            },
        ]
    },
    {
        "registermaps": [
            {
                "mapname": "I2C1 registers",
                "registers": [
                    {
                        "registername": "I2C_CR1",
                        "offset": "0x00",
                        "page": 2559,
                        "chapter": "52.9.1",
                        "resetvalue": "0x00000000",
                        "bits": [
                            {"range": "23", "field": "PECEN", "description": "PEC enable\n"},
                            {"range": "7:4", "field": "DNF", "description": "Digital noise filter\n"},
                            {"range": "0", "field": "PE", "description": "Peripheral enable\n"},
                        ],
                    },
                    {
                        "registername": "I2C_CR2",
                        "offset": "0x04",
                        "page": None,
                        "chapter": None,
                        "resetvalue": "0x00000000",
                        "bits": [{"range": "9:0", "field": "SADD", "description": "SADD\n"}],
                    },
                ],
            }
        ]
    },
]

IMXMAP = [
    {
        "register": "IOMUXC_SW_MUX_CTL_PAD_ENET_TXC",
        "address": "0x30330070",
        "address_cyclic": None,
        "page": 1438,
        "bits": [
            {"range": "4", "field": "SION", "description": "Software Input On Field.\n"},
            {"range": "2-0", "field": "MUX_MODE", "description": "MUX Mode Select Field.\n"},
        ],
    },
    {
        "register": "CCM_GPR0n",
        "address": None,
        "address_cyclic": {
            "base": "0x30380000",
            "offset": "0x0",
            "step": 4,
            "start": 0,
            "end": 3,
        },
        "page": 442,
        "bits": [{"range": "31:0", "field": "GP0", "description": "Timeout cycle count\n"}],
    },
]


@pytest.fixture
def mapdir(tmp_path):
    (tmp_path / "stm32mp157_registers.json").write_text(json.dumps(STM32MAP))
    (tmp_path / "imx8mp_registers.json").write_text(json.dumps(IMXMAP))
    return tmp_path


def regdump(mapdir, soc, regs, *args):
    """run regdump.py without tbot, return the process and the result file"""
    env = dict(os.environ, PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    res = subprocess.run(
        [sys.executable, REGDUMP, "-s", soc, "-i", str(mapdir), "-o", str(mapdir), *args, regs],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    result = mapdir / f"{soc}_result.txt"
    return res, result.read_text() if result.exists() else ""


def test_stm32_register(mapdir):
    res, out = regdump(mapdir, "stm32mp157", '[{"address":"0x40012000","value":"0x00800051"}]')
    assert res.returncode == 0, res.stdout + res.stderr
    assert "register name: I2C_CR1 addr 0x40012000 val: 0x00800051 RM page 2559" in out
    assert "23     PECEN" in out and "val 1" in out
    assert "7:4    DNF                            val 0101" in out
    assert "desc Digital noise filter" in out


def test_stm32_second_instance_and_no_page(mapdir):
    # I2C2 uses the registers of I2C1, at its own base address
    res, out = regdump(mapdir, "stm32mp157", "[{'address':'0x40013004','value':'0x3FF'}]")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "register name: I2C_CR2 addr 0x40013004 val: 0x3FF RM page None" in out
    assert "9:0    SADD                           val 1111111111" in out


def test_stm32_unknown_address(mapdir):
    res, out = regdump(mapdir, "stm32mp157", '[{"address":"0x40012008","value":"0x0"}]')
    assert res.returncode == 0
    assert "address 0x40012008 not found" in res.stdout


def test_stm32_regsfile(mapdir, tmp_path):
    regsfile = tmp_path / "regs.txt"
    regsfile.write_text("I2C_CR1 1 0x00000001\nI2C_NOSUCH 0 0x0\n")
    res, out = regdump(mapdir, "stm32mp157", "[]", "--regsfile", str(regsfile))
    assert res.returncode == 0, res.stdout + res.stderr
    # index 1 is the second peripheral with the registers of I2C1
    assert "register name: I2C_CR1 addr 0x40013000 val: 0x00000001" in out
    assert "register I2C_NOSUCH not found!!" in res.stdout


def test_imx_fixed_address(mapdir):
    res, out = regdump(mapdir, "imx8mp", '[{"address":"0x30330070","value":"0x00000015"}]')
    assert res.returncode == 0, res.stdout + res.stderr
    assert "register name: IOMUXC_SW_MUX_CTL_PAD_ENET_TXC addr 0x30330070" in out
    assert "RM page 1438" in out
    assert "2-0    MUX_MODE                       val 101" in out


def test_imx_cyclic_address(mapdir):
    res, out = regdump(mapdir, "imx8mp", '[{"address":"0x3038000C","value":"0x1"}]')
    assert res.returncode == 0, res.stdout + res.stderr
    assert "register name: CCM_GPR0n addr 0x3038000C" in out


def test_appends_to_the_result(mapdir):
    regs = '[{"address":"0x40012000","value":"0x0"}]'
    regdump(mapdir, "stm32mp157", regs)
    _, out = regdump(mapdir, "stm32mp157", regs)
    assert out.count("register name: I2C_CR1") == 2


@pytest.mark.parametrize(
    "regs,message",
    [
        ("no list", "Invalid format for register list"),
        ('[{"address":"0x40012000"}]', "with 'address' and 'value' keys"),
        ('{"address":"0x40012000","value":"0x0"}', "with 'address' and 'value' keys"),
    ],
)
def test_invalid_register_list(mapdir, regs, message):
    res, out = regdump(mapdir, "stm32mp157", regs)
    assert res.returncode == 1
    assert message in res.stdout
    assert out == ""


def test_runs_without_tbot(mapdir):
    """the subprocess cannot import tbot, so regdump.py did not need it"""
    env = dict(os.environ, PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    check = subprocess.run([sys.executable, "-c", "import tbot"], env=env, capture_output=True)
    if check.returncode == 0:
        pytest.skip("tbot is installed system wide, cannot check without it")
    res, out = regdump(mapdir, "stm32mp157", '[{"address":"0x40012000","value":"0x0"}]')
    assert res.returncode == 0, res.stdout + res.stderr
    assert "register name: I2C_CR1" in out
