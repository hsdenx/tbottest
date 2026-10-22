"""
stm32_rm_descriptions.py - take the descriptions of the bit fields of an
STM32 registermap from the reference manual (PDF) of ST.

The SVD file of ST has every register and bit field, but most field
descriptions are only the name of the field and there is no page of the
reference manual. The reference manual describes every register in a
section of its own, which its table of contents (the outline of the PDF)
lists as "<chapter> <title> (<REGISTERNAME>)" with the page, and every
field of it in the form "Bit 21 I2C1EN: I2C1 peripheral clocks enable" or
"Bits 2:0 I2C12SRC[2:0]: ...", followed by the explanation.

stm32_svd_create_registermap.py uses this with --rm. A text of the
reference manual takes the place of the one a field has, page and chapter
the ones of the register; what the reference manual does not have stays,
e.g. a description taken from an older registermap with -m.
"""

import re
import typing

# lines of the page header and footer, e.g. "Reset and clock control (RCC)
# RM0436", "788/4054 RM0436 Rev 7", "RM0436 Rev 7 789/4054", "1035"
FOOTER = re.compile(
    r"^(?:\d+/\d+ RM\d{4} Rev(?: \d+)?|RM\d{4} Rev(?: \d+)? \d+/\d+|\d{1,4}|.* RM\d{4}|RM\d{4} .*)$"
)

# a footer stuck to the end of a line of text
FOOTER_TAIL = re.compile(r"\s*\d+/\d+ RM\d{4} Rev(?: \d+)?$")

# a heading of a section, e.g. "10.7.117 RCC APB1 ..." or "13.4 GPIO registers"
HEADING = re.compile(r"^(?P<chapter>\d{1,3}\.\d{1,3}(?:\.\d{1,3})?)\s+\S")

# a heading without number, as some chapters have them, e.g. "Extended
# operating mode configuration register (ETH_MACECR)"
UNNUMBERED = re.compile(r"\([A-Za-z][A-Za-z0-9_]*\)$")

# a bit field, e.g. "Bit 21 I2C1EN: ...", "Bits 2:0 I2C12SRC[2:0]: ...",
# "Bits 31:0 MODER[15:0][1:0]: ...", "Bits 27, 21, 11, 5 TCIFx: ..." or
# "Bits 31:0 BKP[31:0]" with the text on the next lines; "Bit 30
# Reserved, must be kept ..." is none
RANGE = r"[0-9a-z+*:]+(?:,\s*[0-9a-z+*:]+)*"
BIT = re.compile(
    rf"^Bits?\s+(?P<range>{RANGE})\s+(?P<field>[A-Za-z][A-Za-z0-9_]*)(?:\[[0-9:]+\])*"
    r"(?:\s*:\s*(?P<text>.*))?$"
)
RESERVED = re.compile(rf"^Bits?\s+{RANGE}\s+Reserved\b")

# the caption of the register summary table at the end of a chapter, e.g.
# "Table 600. ETH register map and reset values"
MAP_TABLE = re.compile(r"^Table\s*\d+\.\s.*register map", re.IGNORECASE)

# the register name in a title of the outline, e.g.
# "13.4.1 GPIO port mode register (GPIOx_MODER) (x = A to K, Z)"
TITLE_NAME = re.compile(r"\(([A-Za-z][A-Za-z0-9_]*_[A-Za-z0-9_]*)\)")


def outline_name(title: str) -> typing.Optional[str]:
    """the register name in a title of the outline, None if there is none"""
    m = TITLE_NAME.search(title or "")
    return m.group(1) if m else None


def index_pattern(name: str) -> "re.Pattern[str]":
    """
    a pattern for the register names a name of the reference manual stands
    for: a lowercase x, y, z or n there is the index of an instance or a
    channel (GPIOx_MODER, MDMA_CxISR, DFSDM_CHyCFGR1, DDRCTRL_PCFGR_x)
    """
    parts = re.split(r"(?<![a-z])[xyzn](?![a-z])", name)
    return re.compile("^" + "[0-9A-Z]{1,2}".join(re.escape(p) for p in parts) + "$")


class RmIndex:
    """the register sections of a reference manual, by register name"""

    def __init__(self, entries: typing.Iterable[typing.Tuple[str, int, str]]) -> None:
        """:param entries: (register name, page, chapter) of the outline"""
        self.exact: typing.Dict[str, typing.Tuple[int, str]] = {}
        self.patterns: typing.List[typing.Tuple["re.Pattern[str]", str]] = []
        for name, page, chapter in entries:
            if name in self.exact:
                continue
            self.exact[name] = (page, chapter)
            if re.search(r"(?<![a-z])[xyzn](?![a-z])", name):
                self.patterns.append((index_pattern(name), name))

    def find(self, names: typing.Iterable[str]) -> typing.Optional[str]:
        """the first name of names the reference manual has, exact or as an
        instance of a name with an index"""
        names = list(names)
        for n in names:
            if n in self.exact:
                return n
        for n in names:
            for pattern, rmname in self.patterns:
                if pattern.match(n):
                    return rmname
        return None


def svd_names(group: str, peripheral: str, name: str) -> typing.List[str]:
    """
    names the reference manual may give a register of the SVD: its own,
    with the group as prefix (CR1 of USART1 is USART_CR1), with the prefix
    of SPI2S as SPI
    """
    names = [name]
    for prefix in (group, re.sub(r"\d+$", "", peripheral)):
        if prefix and not name.startswith(prefix + "_") and f"{prefix}_{name}" not in names:
            names.append(f"{prefix}_{name}")
    if name.startswith("SPI2S_"):
        names.append("SPI_" + name[len("SPI2S_"):])
    return names


def section_lines(
    page_lines: typing.Callable[[int], typing.List[str]], page: int, chapter: str, name: str
) -> typing.List[str]:
    """
    the lines of the section of register name, from its heading (chapter
    and the name in brackets, on the same or the next line) to the next
    heading, without page headers and footers; a heading without number
    (ETH, FMC) shows as the "Address offset" line after it, once bits
    were found

    :param page_lines: function that returns the text lines of a page
    """
    lines: typing.List[str] = []
    started = False
    heading = False
    for pg in range(page, page + 6):
        for raw in page_lines(pg):
            s = FOOTER_TAIL.sub("", raw.strip())
            if not s or FOOTER.match(s):
                continue
            if not started:
                if s.startswith(chapter + " "):
                    heading = True
                if heading and f"({name})" in s:
                    started = True
                continue
            m = HEADING.match(s)
            if m and m.group("chapter") != chapter:
                return lines
            if MAP_TABLE.match(s):
                return lines
            if s.startswith("Address offset") and any(BIT.match(x) for x in lines):
                if lines and UNNUMBERED.search(lines[-1]):
                    lines.pop()
                return lines
            lines.append(s)
    return lines


def parse_bits(lines: typing.List[str]) -> typing.List[dict]:
    """the bit fields of the lines of a section: range, field, description"""
    bits: typing.List[dict] = []
    cur: typing.Optional[dict] = None
    for s in lines:
        if RESERVED.match(s):
            cur = None
            continue
        m = BIT.match(s)
        if m:
            text = m["text"] + "\n" if m["text"] else ""
            cur = {"range": m["range"], "field": m["field"], "description": text}
            bits.append(cur)
        elif cur is not None:
            cur["description"] += s + "\n"
    return bits


def field_description(field: str, rmbits: typing.List[dict]) -> typing.Optional[str]:
    """
    the description of the SVD field field in the fields of the reference
    manual: the one of the same name, of a name with an index for it
    (MODERy for MODER5), or of a name with the number cut off (OT for OT5,
    where the reference manual has Bits 15:0 OT[15:0])
    """
    for b in rmbits:
        if b["field"] == field:
            return b["description"]
    for b in rmbits:
        if re.search(r"(?<![a-z])[xyzn](?![a-z])", b["field"]):
            if index_pattern(b["field"]).match(field):
                return b["description"]
    base = re.sub(r"\d+$", "", field)
    if base != field:
        for b in rmbits:
            if b["field"] == base:
                return b["description"]
    return None


def has_own_description(bit: dict) -> bool:
    """False for a field whose description is only its name, as in the SVD"""
    return bit["description"].strip() != bit["field"]


def apply_rm(
    registermap: list,
    index: RmIndex,
    page_lines: typing.Callable[[int], typing.List[str]],
    groups: typing.Dict[str, str],
) -> typing.Tuple[int, int]:
    """
    take page, chapter and the field descriptions from the reference manual,
    in place of the ones the registermap has

    :param groups: mapname -> (group name, peripheral name) of the SVD
    :returns: number of registers found in the reference manual and of
        field descriptions taken from it
    """
    nregs = nfields = 0
    for regmap in registermap[1]["registermaps"]:
        group, peripheral = groups[regmap["mapname"]]
        for reg in regmap["registers"]:
            rmname = index.find(svd_names(group, peripheral, reg["registername"]))
            if rmname is None:
                continue
            page, chapter = index.exact[rmname]
            rmbits = parse_bits(section_lines(page_lines, page, chapter, rmname))
            if not rmbits:
                continue
            nregs += 1
            reg["page"] = page
            reg["chapter"] = chapter
            for bit in reg["bits"]:
                desc = field_description(bit["field"], rmbits)
                if desc:
                    bit["description"] = desc
                    nfields += 1
    return nregs, nfields


def pdf_outline(pdfpath: str) -> typing.List[typing.Tuple[str, int, str]]:
    """(register name, page, chapter) of every register in the outline of the PDF"""
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdftypes import resolve1

    entries = []
    with open(pdfpath, "rb") as f:
        doc = PDFDocument(PDFParser(f))
        pages = {p.pageid: i + 1 for i, p in enumerate(PDFPage.create_pages(doc))}
        for _level, title, dest, action, _se in doc.get_outlines():
            name = outline_name(title)
            if name is None:
                continue
            d = dest if dest is not None else resolve1(action).get("D") if action else None
            d = resolve1(d)
            if isinstance(d, dict):
                d = resolve1(d.get("D"))
            page = pages.get(d[0].objid) if d else None
            if page is not None:
                entries.append((name, page, title.split()[0]))
    return entries


class PdfPages:
    """the text lines of the pages of a PDF, each page read once"""

    def __init__(self, pdfpath: str) -> None:
        import pdfplumber

        self.pdf = pdfplumber.open(pdfpath)
        self.cache: typing.Dict[int, typing.List[str]] = {}

    def __call__(self, page: int) -> typing.List[str]:
        if page not in self.cache:
            if 1 <= page <= len(self.pdf.pages):
                text = self.pdf.pages[page - 1].extract_text() or ""
            else:
                text = ""
            self.cache[page] = text.split("\n")
        return self.cache[page]
