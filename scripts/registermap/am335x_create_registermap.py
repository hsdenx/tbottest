#!/usr/bin/env python3
"""
am335x_create_registermap.py - create the registermap in JSON format for
the TI AM335x from its Technical Reference Manual (SPRUH73).

usage: am335x_create_registermap.py [-h] -t TRM -o OUTPUT

example:

    $ python3 am335x_create_registermap.py -t spruh73l.pdf -o am335x_registers.json

TI publishes no SVD file for the AM335x. Its reference manual lists every
register in its table of contents (the outline of the PDF) as
"<chapter> <NAME> Register (offset = <hex>h) [reset = <hex>h]" below a
section "<chapter> <MODULE> Registers", and describes the fields of every
register in a table "Bit Field Type Reset Description". The base addresses
of the module instances are in the memory map tables of chapter 2 (L3,
L4_WKUP, L4_PER, L4_FAST), which also give the bus. INSTANCE_MODULES links
an instance of the memory map (UART1) to its module (UART).

The registermap has the format of the STM32MP157 one of registermap.py:
a peripheralmap for every instance, a registermap for every module.
Instances inside a subsystem (CPSW_ALE in CPSW_SS, USB0_CTRL in USBSS, the
parts of the PRU-ICSS) have their offsets in their own chapters, not in
the memory map, and are not in it yet.

Needs pdfplumber.
"""

import argparse
import json
import re
import sys
import threading
import typing

# instance names of the memory map and the module sections they belong to
INSTANCE_MODULES = [
    (r"UART\d", "UART"),
    (r"I2C\d", "I2C"),
    (r"GPIO\d", "GPIO"),
    (r"McSPI\d", "SPI"),
    (r"DMTIMER1_1MS", "DMTIMER_1MS"),
    (r"DMTIMER\d", "TIMER"),
    (r"MMCHS\d|MMC\d", "MULTIMEDIA_CARD"),
    (r"DCAN\d", "DCAN"),
    (r"McASP\d CFG", "MCASP"),
    (r"WDT1", "WATCHDOG_TIMER"),
    (r"RTCSS", "RTC"),
    (r"Control Module", "CONTROL_MODULE"),
    (r"PRM_DEV", "PRM_DEVICE"),
    (r"(CM|PRM)_[A-Z]+", None),
    (r"ADC_TSC", "TSC_ADC_SS"),
    (r"EMIF0", "EMIF4D"),
    (r"TPCC \(EDMA3CC\)", "EDMA3CC"),
    (r"TPTC\d \(EDMA3TC\d\)", "EDMA3TC"),
    (r"Mailbox 0", "MAILBOX"),
    (r"Spinlock", "SPINLOCK"),
    (r"Interrupt controller", "INTC"),
    (r"LCD Controller", "LCD"),
    (r"ELM|GPMC|USBSS|CPSW_SS", None),
]

# a register in the outline
REGISTER = re.compile(
    r"^(?P<chapter>\d+(?:\.\d+)+)\s+(?P<name>\S+) Register "
    r"\(offset = (?P<offset>[0-9A-Fa-f]+)h\) \[reset = (?P<reset>[0-9A-Fa-fX]+)h\]$"
)
# a module section in the outline, e.g. "19.5.1 UART Registers"
MODULE = re.compile(r"^(?P<chapter>\d+(?:\.\d+)+)\s+(?P<name>\S+) Registers$")

# a row of a memory map table of chapter 2
MAPROW = re.compile(
    r"^(?P<name>.*?)\s*0x(?P<start>[0-9A-F]{4}_[0-9A-F]{4})\s+0x(?P<end>[0-9A-F]{4}_[0-9A-F]{4})"
    r"\s+(?P<size>\d+\s?[KMG]?B(?:ytes)?)"
)
MAPTABLE = re.compile(r"^Table 2-\d+\.\s*(?P<bus>L3|L4_WKUP|L4_PER|L4 Fast)\b")

# lines of the page header and footer, e.g. "UART Registers www.ti.com",
# "4268 Universal ... SPRUH73L-October 2011-Revised February 2015"
FOOTER = re.compile(r"www\.ti\.com|SPRUH73|Submit Documentation Feedback|Copyright")

# a row of a field table, e.g. "7-0 THR W 0h Transmit holding register.",
# "31-0 OUTPUTEN[n] R/W FFFFFFFFh ...", "31-16 CPSW_3G_IDENT R-0 0 ..." or
# "31-16 TxRqs_32:17_ R 0h ..." (DCAN, TxRqst[32:17] in the PDF)
FIELDROW = re.compile(
    r"^(?P<range>\d+(?:-\d+)?)\s+(?P<field>[A-Za-z][A-Za-z0-9_:]*)(?:\[[0-9A-Za-z:]+\])?"
    r"\s+(?P<type>[A-Za-z0-9/-]+)\s+(?P<reset>\S+)(?:\s+(?P<text>.*))?$"
)
FIELDHEAD = "Bit Field Type Reset Description"
# where the text of a field table ends
TABLE_END = re.compile(r"^(?:Table|Figure)\s+\d+-\d+\.|^\d+(?:\.\d+){2,}\s+\S")


def parse_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert the AM335x reference manual into a JSON register mapping."
    )
    parser.add_argument("-t", "--trm", required=True, help="reference manual (PDF) of the AM335x")
    parser.add_argument("-o", "--output", required=True, help="JSON file to write")
    return parser.parse_args()


def outline_registers(outline: typing.List[typing.Tuple[int, str, int]]) -> typing.Tuple[list, list]:
    """
    the module sections and the registers of the outline, every register
    with the module section it is in (the innermost one)

    :param outline: (level, title, page) of every entry
    :returns: modules {name, chapter, page}, registers {name, chapter,
        offset, reset, page, module}
    """
    modules = []
    registers = []
    for _level, title, page in outline:
        title = (title or "").replace(" ", " ")
        m = MODULE.match(title)
        if m:
            modules.append({"name": m["name"], "chapter": m["chapter"], "page": page})
            continue
        m = REGISTER.match(title)
        if m:
            owner = None
            for mod in modules:
                if m["chapter"].startswith(mod["chapter"] + "."):
                    if owner is None or len(mod["chapter"]) > len(owner["chapter"]):
                        owner = mod
            registers.append(
                {
                    "name": m["name"],
                    "chapter": m["chapter"],
                    "offset": int(m["offset"], 16),
                    "reset": m["reset"],
                    "page": page,
                    "module": owner["name"] if owner else None,
                }
            )
    return modules, registers


def size_bytes(size: str) -> typing.Optional[int]:
    """the size column of the memory map in bytes, e.g. 4KB, 256 Bytes"""
    m = re.fullmatch(r"(\d+)\s?([KMG]?)B(?:ytes)?", size.strip())
    if not m:
        return None
    return int(m.group(1)) * {"": 1, "K": 1 << 10, "M": 1 << 20, "G": 1 << 30}[m.group(2)]


def memory_map(lines: typing.Iterable[str]) -> typing.List[dict]:
    """
    the instances of the memory map tables of chapter 2: name, start, end,
    size and the bus the table is for; rows without a name (reserved) are
    left out. Where end address and size do not fit (CM_PER 0x44E0_0000 to
    0x44E0_3FFF, 1KB, with CM_WKUP at 0x44E0_0400), the smaller range is
    taken, so the instances do not overlap.
    """
    bus = None
    rows = []
    for line in lines:
        m = MAPTABLE.match(line)
        if m:
            bus = m["bus"].replace("L4 Fast", "L4_FAST")
            continue
        m = MAPROW.match(line)
        if m and bus and m["name"].strip() and m["name"].strip() != "Reserved":
            start = int(m["start"].replace("_", ""), 16)
            end = int(m["end"].replace("_", ""), 16)
            size = size_bytes(m["size"])
            if size is not None:
                end = min(end, start + size - 1)
            rows.append(
                {
                    "name": m["name"].strip(),
                    "start": start,
                    "end": end,
                    "size": m["size"].replace(" Bytes", "B").replace(" ", ""),
                    "bus": bus,
                }
            )
    return rows


def instance_module(name: str, modules: typing.Set[str]) -> typing.Optional[str]:
    """the module section an instance of the memory map belongs to"""
    for pattern, module in INSTANCE_MODULES:
        if re.fullmatch(pattern, name):
            module = module or name
            return module if module in modules else None
    return name if name in modules else None


def field_lines(
    page_lines: typing.Callable[[int], typing.List[str]], page: int, name: str
) -> typing.List[str]:
    """
    the rows of the field table of register name, from the header of the
    table "Table n-m. <name> Register Field Descriptions" over page breaks
    to the next table, figure or heading, without page headers and footers
    """
    caption = re.compile(rf"^Table\s+\d+-\d+\.\s*{re.escape(name)}\s+Register\s+Field\s+Descriptions")
    rows: typing.List[str] = []
    started = False
    for pg in range(page, page + 6):
        for raw in page_lines(pg):
            s = raw.strip()
            if not s or FOOTER.search(s):
                continue
            if not started:
                started = bool(caption.match(s))
                continue
            if s == FIELDHEAD or s.endswith("(continued)"):
                continue
            if TABLE_END.match(s):
                return rows
            rows.append(s)
    return rows


def parse_fields(rows: typing.List[str]) -> typing.List[dict]:
    """the fields of the rows of a field table, highest bits first"""
    fields: typing.List[dict] = []
    cur: typing.Optional[dict] = None
    for s in rows:
        m = FIELDROW.match(s)
        if m:
            text = m["text"] + "\n" if m["text"] else ""
            cur = {"range": m["range"], "field": m["field"], "description": text}
            fields.append(cur)
        elif cur is not None:
            cur["description"] += s + "\n"
    for f in fields:
        if f["field"].upper() == "RESERVED" and not f["description"]:
            f["description"] = "Reserved\n"
    return fields


def size_str(size: int) -> str:
    """size of an address range as the peripheral table writes it, e.g. 4KB"""
    if size % (1024 * 1024) == 0:
        return f"{size // (1024 * 1024)}MB"
    if size % 1024 == 0:
        return f"{size // 1024}KB"
    return f"{size}B"


def build_registermap(
    modules: list,
    registers: list,
    instances: list,
    page_lines: typing.Callable[[int], typing.List[str]],
) -> list:
    """the registermap of the reference manual in the format of registermap.py"""
    names = {m["name"] for m in modules}
    peripheralmaps = []
    used = set()
    for inst in instances:
        module = instance_module(inst["name"], names)
        if module is None:
            continue
        used.add(module)
        peripheralmaps.append(
            {
                "bus": inst["bus"],
                "range": f"0x{inst['start']:08X} - 0x{inst['end']:08X}",
                "size": size_str(inst["end"] - inst["start"] + 1),
                "peripheral": inst["name"],
                "peripheralmap": f"{module} registers",
            }
        )

    registermaps = []
    for module in sorted(used):
        regs = sorted((r for r in registers if r["module"] == module), key=lambda r: r["offset"])
        registermaps.append(
            {
                "mapname": f"{module} registers",
                "registers": [
                    {
                        "registername": r["name"],
                        "offset": f"0x{r['offset']:X}",
                        "page": r["page"],
                        "chapter": r["chapter"],
                        "resetvalue": f"0x{r['reset']}" if r["reset"] != "X" else None,
                        "bits": parse_fields(field_lines(page_lines, r["page"], r["name"])),
                    }
                    for r in regs
                ],
            }
        )
    return [{"peripheralmaps": peripheralmaps}, {"registermaps": registermaps}]


def pdf_outline(pdfpath: str) -> typing.List[typing.Tuple[int, str, int]]:
    """
    (level, title, page) of every entry of the outline of the PDF; the
    outline of the TRM has long chains of entries, which pdfminer walks
    recursively, so this runs with a high recursion limit in a thread with
    a big stack
    """
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdftypes import resolve1

    result: typing.List[typing.Tuple[int, str, int]] = []

    def run() -> None:
        with open(pdfpath, "rb") as f:
            doc = PDFDocument(PDFParser(f))
            pages = {p.pageid: i + 1 for i, p in enumerate(PDFPage.create_pages(doc))}
            for level, title, dest, action, _se in doc.get_outlines():
                d = dest if dest is not None else resolve1(action).get("D") if action else None
                d = resolve1(d)
                if isinstance(d, dict):
                    d = resolve1(d.get("D"))
                try:
                    page = pages.get(d[0].objid) if d else None
                except (AttributeError, TypeError, IndexError):
                    page = None
                if page is not None:
                    result.append((level, title, page))

    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(200000)
    threading.stack_size(512 * 1024 * 1024)
    try:
        t = threading.Thread(target=run)
        t.start()
        t.join()
    finally:
        sys.setrecursionlimit(limit)
        threading.stack_size(0)
    return result


class PdfPages:
    """the text lines of the pages of a PDF, each page read once; the TRM
    needs a small x_tolerance, or pdfplumber drops the spaces"""

    def __init__(self, pdfpath: str) -> None:
        import pdfplumber

        self.pdf = pdfplumber.open(pdfpath)
        self.cache: typing.Dict[int, typing.List[str]] = {}

    def __call__(self, page: int) -> typing.List[str]:
        if page not in self.cache:
            if 1 <= page <= len(self.pdf.pages):
                text = self.pdf.pages[page - 1].extract_text(x_tolerance=1.5) or ""
            else:
                text = ""
            self.cache[page] = text.split("\n")
        return self.cache[page]


def main() -> None:
    args = parse_arguments()
    outline = pdf_outline(args.trm)
    modules, registers = outline_registers(outline)
    pages = PdfPages(args.trm)
    chapter2 = [p for _l, t, p in outline if (t or "").replace(" ", " ").startswith("2 ")]
    chapter3 = [p for _l, t, p in outline if (t or "").replace(" ", " ").startswith("3 ")]
    maplines = [line for pg in range(chapter2[0], chapter3[0]) for line in pages(pg)]
    instances = memory_map(maplines)
    registermap = build_registermap(modules, registers, instances, pages)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(registermap, f, indent=1)
        f.write("\n")
    regs = [r for m in registermap[1]["registermaps"] for r in m["registers"]]
    fields = [b for r in regs for b in r["bits"]]
    print(
        f"{len(modules)} modules, {len(registers)} registers in the outline, "
        f"{len(instances)} instances in the memory map; written to {args.output}: "
        f"{len(registermap[0]['peripheralmaps'])} peripherals, "
        f"{len(registermap[1]['registermaps'])} registermaps, {len(regs)} registers, "
        f"{len(fields)} fields, {sum(1 for r in regs if not r['bits'])} registers without fields"
    )


if __name__ == "__main__":
    main()
