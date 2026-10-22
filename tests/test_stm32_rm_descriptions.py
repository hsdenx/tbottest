"""
Unit tests for scripts/registermap/stm32_rm_descriptions.py, with pages
of text as pdfplumber gives them for the reference manual RM0436: page
header and footer, the register before the heading, the bit table as
garbage, fields over a page break, headings with and without number and
the register map table at the end of a chapter.
"""

import os

import pytest

from conftest import load_module

HERE = os.path.dirname(__file__)
SCRIPTS = os.path.join(HERE, "..", "scripts", "registermap")
rm = load_module("stm32_rm_descriptions", os.path.join(SCRIPTS, "stm32_rm_descriptions.py"))

PAGES = {
    100: [
        "Reset and clock control (RCC) RM0436",
        "Bits 2:0 FRACV[2:0]: belongs to the register before",
        "10.7.117 RCC APB1 peripheral enable for MPU set register",
        "(RCC_MP_APB1ENSETR)",
        "Address offset: 0xA00",
        "Reset value: 0x0000 0000",
        "31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16",
        "NESOIDM",
        "Res.",
        "Bit 31 MDIOSEN: MDIOS peripheral clocks enable",
        "Set by software.",
        "0: disabled",
        "Bit 30 Reserved, must be kept at reset value.",
        "Bits 27, 21 I2CxEN: I2Cx peripheral clocks enable",
        "1: enabled 100/4054 RM0436 Rev 7",
        "100/4054 RM0436 Rev 7",
        "1035",
    ],
    101: [
        "RM0436 Reset and clock control (RCC)",
        "the text of I2CxEN goes on",
        "Bits 15:0 OT[15:0]: Port output type",
        "Bits 31:0 MODER[15:0][1:0]: Port mode",
        "Bits 31:0 BKP[31:0]",
        "Backup data",
        "10.7.118 RCC next register (RCC_NEXT)",
        "Bit 0 NEXT: not ours",
    ],
    200: [
        "63.11.1 Operating mode configuration register (ETH_MACCR)",
        "Address offset: 0x0000",
        "Bit 0 RE: Receiver enable",
        "Table 557. Packet length",
        "Extended operating mode configuration register (ETH_MACECR)",
        "Address offset: 0x0004",
        "Bit 0 GPSLCE: not ours",
    ],
    300: [
        "63.11.9 Last register (ETH_LAST)",
        "Bit 0 LAST: last field",
        "Table 600. ETH register map and reset values",
        "Register name Offset",
    ],
}


def page_lines(page):
    return PAGES.get(page, [])


@pytest.mark.parametrize(
    "title,name",
    [
        ("13.4.1 GPIO port mode register (GPIOx_MODER) (x = A to K, Z)", "GPIOx_MODER"),
        ("10.7.46 RCC I2C1,2 kernel clock selection register (RCC_I2C12CKSELR)", "RCC_I2C12CKSELR"),
        ("13.4 GPIO registers", None),
        ("13.4.2 GPIO register (x = A to K, Z)", None),
    ],
)
def test_outline_name(title, name):
    assert rm.outline_name(title) == name


class TestRmIndex:
    @pytest.fixture
    def index(self):
        return rm.RmIndex(
            [
                ("GPIOx_MODER", 1078, "13.4.1"),
                ("MDMA_CxCR", 1174, "17.5.6"),
                ("USART_CR1", 2626, "53.8.1"),
                ("ETH_MACQ0TxFCR", 3000, "63.11.20"),
                ("USART_CR1", 9999, "99.9.9"),
            ]
        )

    def test_exact_first(self, index):
        assert index.find(["ETH_MACQ0TxFCR"]) == "ETH_MACQ0TxFCR"
        # the first entry of a name counts
        assert index.exact["USART_CR1"] == (2626, "53.8.1")

    def test_index_letters(self, index):
        assert index.find(["GPIOA_MODER"]) == "GPIOx_MODER"
        assert index.find(["MDMA_C31CR"]) == "MDMA_CxCR"

    def test_not_found(self, index):
        assert index.find(["GPIOA_MODERX", "NOSUCH"]) is None


def test_svd_names():
    assert rm.svd_names("USART", "USART1", "CR1") == ["CR1", "USART_CR1"]
    assert rm.svd_names("I2C", "I2C1", "I2C_CR1") == ["I2C_CR1"]
    assert "SPI_CR1" in rm.svd_names("SPI", "SPI1", "SPI2S_CR1")


class TestSectionLines:
    def test_from_heading_to_next_heading(self):
        lines = rm.section_lines(page_lines, 100, "10.7.117", "RCC_MP_APB1ENSETR")
        # nothing of the register before, no header, footer or page number
        assert not any("register before" in s or "RM0436" in s or s == "1035" for s in lines)
        assert lines[0] == "Address offset: 0xA00"
        # over the page break, up to the next numbered heading
        assert "the text of I2CxEN goes on" in lines
        assert lines[-1] == "Backup data"

    def test_footer_at_the_end_of_a_line(self):
        lines = rm.section_lines(page_lines, 100, "10.7.117", "RCC_MP_APB1ENSETR")
        assert "1: enabled" in lines

    def test_heading_without_number(self):
        lines = rm.section_lines(page_lines, 200, "63.11.1", "ETH_MACCR")
        assert lines[-1] == "Table 557. Packet length"
        assert not any("ETH_MACECR" in s or "GPSLCE" in s for s in lines)

    def test_register_map_table(self):
        lines = rm.section_lines(page_lines, 300, "63.11.9", "ETH_LAST")
        assert lines == ["Bit 0 LAST: last field"]

    def test_no_heading(self):
        assert rm.section_lines(page_lines, 100, "10.7.117", "RCC_NOSUCH") == []


class TestParseBits:
    @pytest.fixture
    def bits(self):
        lines = rm.section_lines(page_lines, 100, "10.7.117", "RCC_MP_APB1ENSETR")
        return {b["field"]: b for b in rm.parse_bits(lines)}

    def test_fields(self, bits):
        assert list(bits) == ["MDIOSEN", "I2CxEN", "OT", "MODER", "BKP"]

    def test_reserved_ends_a_field(self, bits):
        assert bits["MDIOSEN"]["description"] == (
            "MDIOS peripheral clocks enable\nSet by software.\n0: disabled\n"
        )

    def test_comma_range_and_page_break(self, bits):
        assert bits["I2CxEN"]["range"] == "27, 21"
        assert bits["I2CxEN"]["description"].endswith("1: enabled\nthe text of I2CxEN goes on\n")

    def test_brackets_and_text_on_the_next_line(self, bits):
        assert bits["MODER"]["description"] == "Port mode\n"
        assert bits["BKP"]["description"] == "Backup data\n"


class TestFieldDescription:
    BITS = [
        {"range": "31", "field": "MDIOSEN", "description": "mdios\n"},
        {"range": "2y+1:2y", "field": "MODERy", "description": "mode\n"},
        {"range": "15:0", "field": "OT", "description": "output type\n"},
    ]

    def test_same_name(self):
        assert rm.field_description("MDIOSEN", self.BITS) == "mdios\n"

    def test_index_letter(self):
        assert rm.field_description("MODER5", self.BITS) == "mode\n"

    def test_number_cut_off(self):
        assert rm.field_description("OT12", self.BITS) == "output type\n"

    def test_none(self):
        assert rm.field_description("NOSUCH", self.BITS) is None


def test_has_own_description():
    assert not rm.has_own_description({"field": "UE", "description": "UE\n"})
    assert rm.has_own_description({"field": "UE", "description": "USART enable\n"})


def test_apply_rm():
    registermap = [
        {"peripheralmaps": []},
        {
            "registermaps": [
                {
                    "mapname": "RCC registers",
                    "registers": [
                        {
                            "registername": "RCC_MP_APB1ENSETR",
                            "offset": "0xA00",
                            "page": 5,
                            "chapter": "1.1",
                            "resetvalue": "0x00000000",
                            "bits": [
                                {"range": "31", "field": "MDIOSEN", "description": "old text\n"},
                                {"range": "21", "field": "I2C1EN", "description": "I2C1EN\n"},
                                {"range": "0", "field": "TIM2EN", "description": "from -m\n"},
                            ],
                        },
                        {
                            "registername": "RCC_NOSUCH",
                            "offset": "0xA04",
                            "page": None,
                            "chapter": None,
                            "resetvalue": "0x00000000",
                            "bits": [{"range": "0", "field": "X", "description": "X\n"}],
                        },
                    ],
                }
            ]
        },
    ]
    index = rm.RmIndex([("RCC_MP_APB1ENSETR", 100, "10.7.117")])
    groups = {"RCC registers": ("RCC", "RCC")}
    assert rm.apply_rm(registermap, index, page_lines, groups) == (1, 2)
    found, notfound = registermap[1]["registermaps"][0]["registers"]
    assert (found["page"], found["chapter"]) == (100, "10.7.117")
    texts = {b["field"]: b["description"] for b in found["bits"]}
    # the reference manual takes the place of the old text, I2C1EN from
    # I2CxEN, TIM2EN keeps what it had
    assert texts["MDIOSEN"].startswith("MDIOS peripheral clocks enable")
    assert texts["I2C1EN"].startswith("I2Cx peripheral clocks enable")
    assert texts["TIM2EN"] == "from -m\n"
    assert notfound["page"] is None and notfound["bits"][0]["description"] == "X\n"


def test_no_pdfplumber_at_import():
    """the converter imports this module without --rm, pdfplumber must not
    be needed for that"""
    src = open(os.path.join(SCRIPTS, "stm32_rm_descriptions.py")).read()
    head = src[: src.index("def outline_name")]
    assert "pdfplumber" not in head.replace("pdfplumber is", "").split('"""', 2)[-1]
    assert "pdfminer" not in head.split('"""', 2)[-1]
