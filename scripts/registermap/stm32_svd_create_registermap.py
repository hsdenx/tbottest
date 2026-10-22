#!/usr/bin/env python3
"""
stm32_svd_create_registermap.py - create the registermap in JSON format for
STM32MP1 SoCs from the SVD file of ST.

usage: stm32_svd_create_registermap.py [-h] -s SVD [-m MERGE] [--rm RM] -o OUTPUT

example:

    $ wget -U "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)" \\
        https://www.st.com/resource/en/svd/stm32mp1-svd.zip
    $ unzip stm32mp1-svd.zip
    $ python3 stm32_svd_create_registermap.py \\
        -s STM32MP1_svd/STM32MP1_svd_v1.1/STM32MP157x.svd \\
        -m stm32mp157_registers.json --rm rm0436.pdf -o stm32mp157_registers.json

The SVD has every peripheral with its base address, every register with
offset and reset value and every bit field with its position, but most
field descriptions are only the name of the field and there is no page
of the reference manual. With -m the bus of every peripheral, and the
descriptions, pages and chapters of an existing registermap (e.g. made
with stm32mp157_create_registermap.py from the reference manual) are
taken over, register by register at the same address, field by field of
the same name or bit range.

With --rm the descriptions of the fields, and page and chapter of the
registers, are taken from the reference manual (PDF) in place of the
ones of the SVD or of -m, where the reference manual has them, see
stm32_rm_descriptions.py; that needs pdfplumber.
"""

import argparse
import json
import typing
import xml.etree.ElementTree as ET

# only re and typing at import, pdfplumber is loaded for --rm only
from stm32_rm_descriptions import FOOTER, FOOTER_TAIL


def parse_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert an STM32 SVD file into a JSON register mapping."
    )
    parser.add_argument("-s", "--svd", required=True, help="SVD file of ST")
    parser.add_argument(
        "-m", "--merge", help="existing registermap to take descriptions and pages from"
    )
    parser.add_argument(
        "--rm", help="reference manual (PDF) to take the missing descriptions from"
    )
    parser.add_argument("-o", "--output", required=True, help="JSON file to write")
    return parser.parse_args()


def text(elem: ET.Element, tag: str, default: str = "") -> str:
    """text of the child tag of elem, whitespace collapsed"""
    value = elem.findtext(tag)
    if value is None:
        return default
    return " ".join(value.split())


def size_str(size: int) -> str:
    """size of an address block as the peripheral table writes it, e.g. 8KB"""
    if size % (1024 * 1024) == 0:
        return f"{size // (1024 * 1024)}MB"
    if size % 1024 == 0:
        return f"{size // 1024}KB"
    return f"{size}B"


def bit_range(field: ET.Element) -> str:
    """bit range of a field as "msb:lsb", or "bit" for a single bit"""
    if field.find("bitOffset") is not None:
        lsb = int(text(field, "bitOffset"), 0)
        msb = lsb + int(text(field, "bitWidth", "1"), 0) - 1
    elif field.find("lsb") is not None:
        lsb = int(text(field, "lsb"), 0)
        msb = int(text(field, "msb"), 0)
    else:
        msb, lsb = (int(v) for v in text(field, "bitRange").strip("[]").split(":"))
    return str(lsb) if msb == lsb else f"{msb}:{lsb}"


def svd_registers(peripheral: ET.Element) -> typing.List[dict]:
    """the registers of a peripheral in the format of the registermap"""
    registers = []
    regs = peripheral.find("registers")
    for reg in regs.iter("register") if regs is not None else []:
        fields = sorted(
            reg.iter("field"),
            key=lambda f: int(bit_range(f).split(":")[0]),
            reverse=True,
        )
        registers.append(
            {
                "registername": text(reg, "name"),
                "offset": f"0x{int(text(reg, 'addressOffset'), 0):02X}",
                "page": None,
                "chapter": None,
                "resetvalue": text(reg, "resetValue") or None,
                "bits": [
                    {
                        "range": bit_range(f),
                        "field": text(f, "name"),
                        "description": text(f, "description") + "\n",
                    }
                    for f in fields
                ],
            }
        )
    return registers


def svd_to_registermap(root: ET.Element) -> list:
    """
    the registermap of an SVD file: peripheralmaps with the address range
    of every peripheral, registermaps with the registers of every
    peripheral that is not derived from another one; a derived peripheral
    points to the registermap of the one it is derived from
    """
    peripherals = root.find("peripherals").findall("peripheral")
    byname = {text(p, "name"): p for p in peripherals}

    def base_of(p: ET.Element) -> ET.Element:
        while p.get("derivedFrom"):
            p = byname[p.get("derivedFrom")]
        return p

    peripheralmaps = []
    registermaps = []
    for p in peripherals:
        base = base_of(p)
        mapname = f"{text(base, 'name')} registers"
        block = base.find("addressBlock")
        start = int(text(p, "baseAddress"), 0) + int(text(block, "offset"), 0)
        size = int(text(block, "size"), 0)
        peripheralmaps.append(
            {
                "bus": None,
                "range": f"0x{start:08X} - 0x{start + size - 1:08X}",
                "size": size_str(size),
                "peripheral": text(p, "name"),
                "peripheralmap": mapname,
            }
        )
        if base is p:
            registermaps.append({"mapname": mapname, "registers": svd_registers(p)})

    return [{"peripheralmaps": peripheralmaps}, {"registermaps": registermaps}]


def merge_bus(registermap: list, old: list) -> int:
    """
    take the bus of every peripheral from the peripheral table of the
    registermap old (made from the memory map of the reference manual,
    the SVD has no bus), from the entry whose address range holds the base
    address of the peripheral, so a part of a peripheral (ADC2 in the ADC
    block) gets the bus as well

    :returns: number of peripherals with a bus now
    """
    ranges = []
    for p in old[0]["peripheralmaps"]:
        start, end = (int(a, 16) for a in p["range"].split(" - "))
        ranges.append((start, end, p["bus"]))

    n = 0
    for p in registermap[0]["peripheralmaps"]:
        start = int(p["range"].split(" - ")[0], 16)
        bus = next((b for s, e, b in ranges if s <= start <= e and b), None)
        if bus is not None:
            p["bus"] = bus
            n += 1
    return n


def clean_description(desc: str) -> str:
    """a description without the page headers and footers an older
    extraction from the reference manual left in it"""
    lines = []
    for line in desc.split("\n"):
        if line.strip() and FOOTER.match(line.strip()):
            continue
        cut = FOOTER_TAIL.sub("", line)
        if line.strip() and not cut.strip():
            continue
        lines.append(cut)
    return "\n".join(lines)


def map_pairs(registermap: list, old: list) -> typing.List[typing.Tuple[dict, dict]]:
    """
    pairs of an old registermap and the new one of the peripheral at the
    same base address, as the peripheral tables of both say
    """
    newstart = {}
    for p in registermap[0]["peripheralmaps"]:
        newstart.setdefault(int(p["range"].split(" - ")[0], 16), p["peripheralmap"])
    newmaps = {m["mapname"]: m for m in registermap[1]["registermaps"]}
    oldmaps = {m["mapname"]: m for m in old[1]["registermaps"]}

    pairs = []
    for p in old[0]["peripheralmaps"]:
        oldmap = oldmaps.get(p["peripheralmap"])
        newname = newstart.get(int(p["range"].split(" - ")[0], 16))
        if oldmap is None or newname is None:
            continue
        pair = (oldmap, newmaps[newname])
        if all(pair[0] is not a or pair[1] is not b for a, b in pairs):
            pairs.append(pair)
    return pairs


def merge_descriptions(registermap: list, old: list) -> typing.Tuple[int, int]:
    """
    take descriptions, page and chapter from the registermap old, made
    from the reference manual, where it names the registers otherwise
    (USART_CR1 for CR1 of USART1, GPIOx_MODER for GPIOA_MODER): a register
    of an old registermap is taken for the register at the same offset of
    the peripheral at the same base address, a field for the field of the
    same name, else of the same bit range

    :returns: number of registers and of fields taken over
    """
    nregs = nfields = 0
    for oldmap, newmap in map_pairs(registermap, old):
        byoffset = {}
        for reg in oldmap["registers"]:
            # the first one of an offset, not an "-alternate" view of it
            byoffset.setdefault(int(reg["offset"], 16), reg)
        for reg in newmap["registers"]:
            oldreg = byoffset.get(int(reg["offset"], 16))
            if oldreg is None or reg["page"] is not None:
                continue
            nregs += 1
            reg["page"] = oldreg.get("page")
            reg["chapter"] = oldreg.get("chapter")
            byfield = {b["field"]: b["description"] for b in oldreg["bits"]}
            byrange = {b["range"]: b["description"] for b in oldreg["bits"]}
            for bit in reg["bits"]:
                desc = byfield.get(bit["field"], byrange.get(bit["range"]))
                if desc is not None:
                    bit["description"] = clean_description(desc)
                    nfields += 1
    return nregs, nfields


def map_groups(root: ET.Element) -> typing.Dict[str, typing.Tuple[str, str]]:
    """mapname -> (group name, peripheral name) of every registermap of the SVD"""
    groups = {}
    for p in root.find("peripherals").findall("peripheral"):
        if not p.get("derivedFrom"):
            name = text(p, "name")
            groups[f"{name} registers"] = (text(p, "groupName"), name)
    return groups


def main() -> None:
    args = parse_arguments()
    root = ET.parse(args.svd).getroot()
    registermap = svd_to_registermap(root)
    if args.merge:
        with open(args.merge, encoding="utf-8") as f:
            old = json.load(f)
        nregs, nfields = merge_descriptions(registermap, old)
        nbus = merge_bus(registermap, old)
        print(f"took over {nregs} registers and {nfields} field descriptions from {args.merge}")
        print(f"took over the bus of {nbus} peripherals from {args.merge}")
    if args.rm:
        # needs pdfplumber, only loaded for --rm
        import stm32_rm_descriptions as rmdesc

        index = rmdesc.RmIndex(rmdesc.pdf_outline(args.rm))
        nregs, nfields = rmdesc.apply_rm(
            registermap, index, rmdesc.PdfPages(args.rm), map_groups(root)
        )
        print(f"found {nregs} registers in {args.rm}, took {nfields} field descriptions")
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(registermap, f, indent=1)
        f.write("\n")
    nregs = sum(len(m["registers"]) for m in registermap[1]["registermaps"])
    print(
        f"{len(registermap[0]['peripheralmaps'])} peripherals, "
        f"{len(registermap[1]['registermaps'])} registermaps, {nregs} registers "
        f"written to {args.output}"
    )


if __name__ == "__main__":
    main()
