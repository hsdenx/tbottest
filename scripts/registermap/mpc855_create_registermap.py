#!/usr/bin/env python3
"""
mpc855_create_registermap.py - create the registermap in JSON format for
the PowerPC MPC855T from its user's manual (MPC855TUM).

usage: mpc855_create_registermap.py [-h] -u MANUAL -o OUTPUT

example:

    $ python3 mpc855_create_registermap.py -u MPC855TUM.pdf -o mpc855_registers.json

The registers of the MPC855T lie in a 16 Kbyte block at the address of the
internal memory map register (IMMR), which a board sets (U-Boot
CONFIG_SYS_IMMR). The registermap keeps the offsets in that block and
says so with "relative_to": "IMMR"; who uses it gives the base, see
REGISTERMAP of registermap.py and the board key registermap_base.

Table 2-1 "MPC855T Internal Memory Map" of the manual lists every
register with its offset, name, size and the section that describes it,
grouped by block (General System Interface Unit, PCMCIA, Memory
Controller, ...). Each section has a table "<NAME> Field Descriptions"
with the fields as "Bits Name Description".

The manual numbers the bits from the most significant one (bit 0), the
registermap from the least significant one. A dump reads a 32-bit word at
the address of a register, and on the big-endian PowerPC bit 0 of a 32,
16 or 8 bit register is bit 31 of that word, so bit b becomes 31 - b.
A 16 or 8 bit register at an address that is not 32-bit aligned can not
be read as a word.

The registermap has the format of the STM32MP157 one of registermap.py:
a peripheralmap and a registermap for every block of Table 2-1, the
ranges of the peripheralmaps offsets to the IMMR.

Needs pdfplumber.
"""

import argparse
import json
import re
import typing

# a block heading of Table 2-1, a row without offset
# a register row of Table 2-1, e.g.
# "000 SIUMCR—SIU module configuration register 32 bits 10.4.2/-5"
MAPROW = re.compile(
    r"^(?P<offset>[0-9A-F]{3,4})\s+(?P<name>[A-Z][A-Z0-9_]*)\s*—\s*(?P<desc>.*?)\s+"
    r"(?P<size>8|16|32)\s+bits?\s+(?P<section>\d+(?:\.\d+)+)/-?\d+\s*$"
)
# a reserved row, e.g. "008–00D Reserved 6 bytes —"
MAPRESERVED = re.compile(r"^[0-9A-F]{3,4}(?:–[0-9A-F]{3,4})?\s+Reserved\b")
MAPTABLE = re.compile(r"^Table 2-1\.\s")
# where Table 2-1 ends
MAPEND = re.compile(r"^(?:Table 2-2\.|Chapter 3\b)")

# lines of the page header and footer
FOOTER = re.compile(r"^(?:Chapter \d+\.\s.*|MPC855T User.s Manual|\d+-\d+|Part [IVX]+\b.*)$")

# a heading of a section, e.g. "10.4.2 SIU Module Configuration Register (SIUMCR)"
HEADING = re.compile(r"^(?P<section>\d+(?:\.\d+)+)\s+[A-Z]")
# the caption of a field table
FIELDTABLE = re.compile(r"^Table \d+-\d+\.\s.*(?:Field|Bit) Descriptions")
FIELDHEAD = re.compile(r"^Bits?\s+Name\s+Description")
# a row of a field table, e.g. "0–15 ISB Internal space base. ...",
# "16 — Reserved", "8–12, 14 ODn Tells how ..." or "0–7, 13, 15 — Reserved"
BITS = r"\d{1,2}(?:\s*[–-]\s*\d{1,2})?"
FIELDROW = re.compile(
    rf"^(?P<bits>{BITS}(?:,\s*{BITS})*)\s+"
    r"(?P<field>[A-Z][A-Z0-9_]*[a-z]?(?:\[[0-9:–-]+\])?|—)(?:\s+(?P<text>.*))?$"
)
TABLE_END = re.compile(r"^(?:Table|Figure)\s+\d+-\d+\.")
# a line of the table of contents, ends with the page, e.g. "...(SIUMCR) 10-5"
TOC_LINE = re.compile(r"(?:\.\s*){3,}|\s\d+-\d+$")


def parse_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert the MPC855T user's manual into a JSON register mapping."
    )
    parser.add_argument("-u", "--manual", required=True, help="user's manual (PDF) of the MPC855T")
    parser.add_argument("-o", "--output", required=True, help="JSON file to write")
    return parser.parse_args()


def memory_map(lines: typing.Iterable[str]) -> typing.List[dict]:
    """
    the registers of Table 2-1: offset, name, size in bits, section and the
    block (the heading row above them)
    """
    rows = []
    block = None
    intable = False
    for line in lines:
        s = line.strip()
        if MAPTABLE.match(s):
            intable = True
            continue
        if not intable:
            continue
        if MAPEND.match(s):
            break
        if not s or FOOTER.match(s) or s.startswith("Offset Name Size"):
            continue
        m = MAPROW.match(s)
        if m:
            rows.append(
                {
                    "offset": int(m["offset"], 16),
                    "name": m["name"],
                    "size": int(m["size"]),
                    "section": m["section"],
                    "block": block,
                }
            )
            continue
        if MAPRESERVED.match(s) or re.match(r"^[0-9A-F]{3,4}\b", s):
            continue
        # a block heading starts with a capital and has no offset; a line
        # that continues the description of a row starts lower case
        if s[0].isupper() and len(s) < 60:
            block = s
    return rows


def bit_ranges(bits: str) -> typing.List[typing.Tuple[int, typing.Optional[int]]]:
    """the ranges of the bits column, e.g. "8–12, 14" -> [(8, 12), (14, None)]"""
    ranges = []
    for part in bits.split(","):
        nums = [int(n) for n in re.split(r"\s*[–-]\s*", part.strip())]
        ranges.append((nums[0], nums[1] if len(nums) > 1 else None))
    return ranges


def lsb_range(first: int, last: typing.Optional[int]) -> str:
    """the bit range of the manual (bit 0 the most significant) as range
    of the registermap (bit 0 the least significant) in the 32-bit word a
    dump reads"""
    if last is None or last == first:
        return str(31 - first)
    return f"{31 - first}-{31 - last}"


def field_rows(lines: typing.List[str], section: str) -> typing.List[str]:
    """
    the rows of the first field table after the heading of section, up to
    the next table, figure or heading; empty if the section has no field
    table before the next section
    """
    started = intable = False
    rows: typing.List[str] = []
    for s in lines:
        h = HEADING.match(s)
        if not started:
            started = bool(h and h["section"] == section)
            continue
        if not intable:
            if h and h["section"] != section and not h["section"].startswith(section + "."):
                return []
            intable = bool(FIELDTABLE.match(s))
            continue
        if FIELDHEAD.match(s) or s.endswith("(continued)"):
            continue
        if TABLE_END.match(s) or (h and not FIELDROW.match(s)):
            return rows
        rows.append(s)
    return rows


def parse_fields(rows: typing.List[str]) -> typing.List[dict]:
    """
    the fields of the rows of a field table, bit ranges converted; a row
    with a list of bits ("8–12, 14 ODn") gives a field for every range,
    with the same name and description
    """
    fields: typing.List[dict] = []
    cur: typing.List[dict] = []
    lastbit = -1
    for s in rows:
        m = FIELDROW.match(s)
        # the fields count up from bit 0; a line of values ("0 Disable the
        # bus monitor.") starts with a bit the fields have passed already
        if m and bit_ranges(m["bits"])[0][0] <= lastbit:
            m = None
        if m:
            lastbit = max(last if last is not None else first for first, last in bit_ranges(m["bits"]))
            name = m["field"]
            name = "Reserved" if name == "—" else re.sub(r"\[.*\]$", "", name)
            text = m["text"] + "\n" if m["text"] else ("Reserved\n" if name == "Reserved" else "")
            cur = [
                {"range": lsb_range(first, last), "field": name, "description": text}
                for first, last in bit_ranges(m["bits"])
            ]
            fields.extend(cur)
        else:
            for f in cur:
                f["description"] += s + "\n"
    return fields


def content_lines(
    page_lines: typing.Callable[[int], typing.List[str]], npages: int
) -> typing.List[typing.Tuple[int, str]]:
    """(page, line) of every page, without headers and footers; the first
    line of a page is its running header, unless it is a heading"""
    out = []
    for pg in range(1, npages + 1):
        for i, raw in enumerate(page_lines(pg)):
            s = raw.strip()
            if not s or FOOTER.match(s):
                continue
            if i == 0 and not HEADING.match(s) and not MAPTABLE.match(s):
                continue
            out.append((pg, s))
    return out


def build_registermap(lines: typing.List[typing.Tuple[int, str]]) -> list:
    """
    the registermap of the manual in the format of registermap.py, with
    offsets to the IMMR
    """
    text = [s for _p, s in lines]
    rows = memory_map(text)
    # first line of every section heading after the table of contents and
    # the lists of figures and tables: from the first row of Table 2-1 on,
    # and not a line that ends with a page as "10-5"
    first = next((i for i, s in enumerate(text) if MAPROW.match(s)), 0)
    starts = {}
    for i in range(first, len(lines)):
        s = text[i]
        h = HEADING.match(s)
        if h and h["section"] not in starts and not TOC_LINE.search(s):
            starts[h["section"]] = i

    blocks: typing.Dict[str, list] = {}
    for r in rows:
        blocks.setdefault(r["block"], []).append(r)

    peripheralmaps = []
    registermaps = []
    names = sorted(blocks, key=lambda b: min(r["offset"] for r in blocks[b]))
    for i, block in enumerate(names):
        regs = blocks[block]
        start = min(r["offset"] for r in regs)
        if i + 1 < len(names):
            end = min(r["offset"] for r in blocks[names[i + 1]]) - 1
        else:
            end = max(r["offset"] + r["size"] // 8 for r in regs) - 1
        mapname = f"{block} registers"
        peripheralmaps.append(
            {
                "bus": "IMMR",
                "range": f"0x{start:08X} - 0x{end:08X}",
                "size": f"{end - start + 1}B",
                "peripheral": block,
                "peripheralmap": mapname,
            }
        )
        registers = []
        for r in regs:
            pos = starts.get(r["section"])
            fields = []
            page = None
            if pos is not None:
                page = lines[pos][0]
                fields = parse_fields(field_rows(text[pos:pos + 400], r["section"]))
            registers.append(
                {
                    "registername": r["name"],
                    "offset": f"0x{r['offset'] - start:X}",
                    "page": page,
                    "chapter": r["section"],
                    "resetvalue": None,
                    "size": r["size"],
                    "bits": fields,
                }
            )
        registermaps.append({"mapname": mapname, "registers": registers})
    return [{"peripheralmaps": peripheralmaps, "relative_to": "IMMR"}, {"registermaps": registermaps}]


class PdfPages:
    """the text lines of the pages of a PDF, each page read once"""

    def __init__(self, pdfpath: str) -> None:
        import pdfplumber

        self.pdf = pdfplumber.open(pdfpath)
        self.cache: typing.Dict[int, typing.List[str]] = {}

    def __len__(self) -> int:
        return len(self.pdf.pages)

    def __call__(self, page: int) -> typing.List[str]:
        if page not in self.cache:
            text = self.pdf.pages[page - 1].extract_text(x_tolerance=1.5) or ""
            self.cache[page] = text.split("\n")
        return self.cache[page]


def main() -> None:
    args = parse_arguments()
    pages = PdfPages(args.manual)
    lines = content_lines(pages, len(pages))
    registermap = build_registermap(lines)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(registermap, f, indent=1)
        f.write("\n")
    regs = [r for m in registermap[1]["registermaps"] for r in m["registers"]]
    print(
        f"{len(registermap[0]['peripheralmaps'])} blocks, {len(regs)} registers, "
        f"{sum(len(r['bits']) for r in regs)} fields, "
        f"{sum(1 for r in regs if not r['bits'])} registers without fields, "
        f"written to {args.output}"
    )


if __name__ == "__main__":
    main()
