#!/usr/bin/env python3
"""
nxp_imx_create_registermap.py - create a registermap in JSon format for NXP SoCs.

usage: nxp_imx_create_registermap.py [-h] -s SOC

example:

    $ python3 nxp_imx_create_registermap.py -s imx8mp
"""

import argparse
import pdfplumber
import re
import json


def parse_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert NXP RM (pdf format) into JSON register mapping."
    )

    parser.add_argument(
        "-s", "--soc", required=True, help="Name of the SoC (example imx8mp)"
    )

    args = parser.parse_args()
    return args


class pdf2json:
    """ """

    def __init__(self, socname: str) -> None:
        self.soc = socname
        self.page = None
        self.page_nr = None
        self.peripheralmaps = []
        self.peripheralmapranges = {"start_page": 161, "end_page": 168}

        self.registermaps = []

        if self.soc == "stm32mp157":
            self.peripheralmapranges = {"start_page": 161, "end_page": 168}
            self.pdfname = "mp157-rm0436-DM00327659.pdf"
            self.path = "/home/hs/data/Entwicklung/prozessordoku/stm32/mp15"
            self.url = "https://www.st.com/resource/en/reference_manual/DM00327659.pdf"
            self.output_file = f"{self.soc}_registers.json"
        else:
            raise RuntimeError(f"Soc {self.soc} not supported yet.")

    def debug(self, msg):
        print(msg)

    def converthex(self, val):
        if val[-1] == "h":
            val = "0x" + val[:-1]

        return val

    def print_all_tables(self):
        tables =self.page.extract_tables()
        self.debug(f"\nfound tables: {len(tables)}")

        for t_idx, table in enumerate(tables):
            self.debug(f"\n--- Table {t_idx+1} ---")
            for row in table:
                self.debug(row)


    def create_register_map(self, pdf, mapname):
        #
        #   {     
        #    "mapname" : "USART registers",  # same as peripheralmap
        #    "registername" : "USART_CR1",   # from within (xxxx)
        #    "offset" : "0",                 # from line Address offset
        #    "page": 2626,
        #    "bits": [
        #      { 
        #        "range": "31",
        #        "field": "RXFFIE",
        #        "description": "RXFIFO full interrupt enable\nThis bit is set and cleared by software.\n0: Interrupt inhibited\n1: USART interrupt generated when RXFF = 1 in the USART_ISR register"
        #      },
        #      {
        #        "range": "25:21",
        #        "field": "DEAT[4:0]",       
        #        "description":"Driver enable assertion time\nThis 5-bit value defines the time between the activation of the DE (Driver Enable) signal and\nthe beginning of the start bit. It is expressed in sample time units (1/8 or 1/16 bit time,\n\ndepending on the oversampling rate).\nThis bitfield can only be written when the USART is disabled (UE = 0).\nnote: If the Driver Enable feature is not supported, this bit is reserved and must be kept at\nreset value. Refer to Section 53.4: USART implementation on page 2577.\n"
        #      },
        #    ]   
        #  },
        #

        for rm in self.registermaps:
            if rm["mapname"] == mapname:
                self.debug(f"registermap {mapname} already created!")
                return

        self.debug(f"==== Create registermap {mapname} ====")
        # ToDo get rid of this
        # currently scanning the whole pdf for each register, exhausts memory
        if mapname == "ADC registers (for each ADC)":
            start_page = 1577
            end_page = 1610
        elif mapname == "DDRCTRL registers":
            start_page = 219
            end_page = 302
        elif mapname == "PUBL registers":
            start_page = 378
            end_page = 421
        elif mapname == "DTS registers":
            start_page = 1631
            end_page = 1639
        elif mapname == "I2C registers":
            start_page = 2559
            end_page = 2573
        elif mapname == "GPIO registers":
            start_page = 1078
            end_page = 1092
        elif mapname == "SPI/I2S registers":
            start_page = 2723
            end_page = 2743
        elif mapname == "SYSCFG registers":
            start_page = 1097
            end_page = 1114
        elif mapname == "USART registers":
            start_page = 2626
            end_page = 2670
        else:
            self.debug(f"==== Create registermap {mapname} not yet supported ====")
            return

        registers = []
        foundchapter = False
        chapter = None

        regname = None
        offset = None
        page = None
        resetvalue = None
        bits = []
        bitstemp = None
        foundaddress = False
        foundreset = False
        foundbits = False

        for page_num in range(start_page - 1, end_page):
            self.page = pdf.pages[page_num]
            self.page_nr = page_num + 1
            self.debug(f"\n=== Page {self.page_nr} ===\n")
            self.debug(f"\n=== Page {self.page_nr} start with analysing text ===\n")
            text = self.page.extract_text()
            if text:
                lines = text.split("\n")
                oldline = None
                for line_num, line in enumerate(lines, start=1):
                    self.debug(f"one line {self.page} nr {self.page_nr}")
                    line = line.strip()
                    if not line:
                        continue

                    self.debug(f"LINE {line_num}: {line} {foundchapter} {foundaddress} {foundreset}")
                    # first search for the chapter
                    if foundchapter == False:
                        #pattern = rf"\b\d{{1,3}}\.\d+\s+{re.escape(mapname)}\b"
                        pattern = rf"(?P<chapter>\d{{1,3}}\.\d+)\s+{re.escape(mapname)}"
                        m = re.search(pattern, line)
                        if m:
                            page = self.page_nr
                            foundchapter = True
                            chapter = m.group("chapter")
                            chapterstart = m.group("chapter")
                            self.debug(f"LINE {line_num}: {line} ==== found chapter {mapname} {chapter}")

                        oldline = line
                        continue
                    else:
                        # search for "chapterstart.X .... map" -> end of register description
                        #
                        #if self.page_nr > 2742 and self.page_nr < 2744:
                        #    self.debug(f"LINE {line_num}: {line} ==== search end chapter {mapname} {chapter} {chapterstart}")
                        #
                        # DDRCTRL registers summary
                        #
                        foundEnd = False
                        pattern = re.compile(
                            r'^(?P<chapter>\d{1,3}\.\d{1,3}(?:\.\d{1,3})?)\b.*\b(?:register map|common registers)\b',
                            flags=re.IGNORECASE
                        )
                        m = re.search(pattern, line)
                        if m:
                            self.debug(f"LINE {line_num}: {line} ==== found other chapter than {mapname} END ====")
                            foundEnd = True

                        pattern = rf"(?P<chapterstart>{re.escape(chapterstart)}\.\d+)\s+.*map and reset values$"
                        m = re.search(pattern, line)
                        if m:
                            self.debug(f"LINE {line_num}: {line} ==== found other chapter than {mapname} END ====")
                            foundEnd = True

                        if "DDRCTRL registers summary" in line:
                            self.debug(f"LINE {line_num}: {line} ==== found other chapter than {mapname} END ====")
                            foundEnd = True

                        if foundEnd:
                            if regname:
                                if bitstemp:
                                    self.debug(f"LINE {line_num}: {line} ==== commit bitstemp {bitstemp}")
                                    bits.append(bitstemp)
                                registers.append(
                                    {
                                        "registername" : regname,
                                        "offset" : offset,
                                        "page" : page,
                                        "resetvalue": resetvalue,
                                        "bits" : bits,
                                    }
                                )

                            self.registermaps.append(
                                {
                                    "mapname" : mapname,
                                    "registers" : registers,
                                }
                            )
                            return

                    # when we have the chapter search for registername
                    #
                    # problem () in next line
                    # LINE 2: 14.3.2 SYSCFG peripheral mode configuration set register
                    # LINE 3: (SYSCFG_PMCSETR) True True True
                    #
                    #pattern = r"(?P<chapter>\d{1,3}\.\d+\.\d+)\s+[^()]*\((?P<regname>[^()]+)\)"
                    if line[0] == "(" and line[1] == "S":
                        self.debug(f"LINE {line_num}: ==== line start with (S {oldline}")
                        if oldline:
                            pattern = re.compile(
                                r'(?P<chapter>\b(?P<x>\d{1,3})\.(?P<y>\d{1,3})(?:\.(?P<z>\d{1,3}))?)\b(?:(?!register).)*\bregister\b',
                                re.IGNORECASE
                            )
                            m = re.search(pattern, oldline)
                            self.debug(f"LINE {line_num}: ==== line start with (S {oldline} m {m}")
                            if m:
                                self.debug(f"LINE {line_num}: ==== oldline has chapter {m.group('chapter')}")
                                line = oldline + line

                    pattern = r"(?P<chapter>\d{1,3}\.\d+\.\d+)\s+(?:[^()\[]*\s*)?(?P<alt>\[alternate\])?\s*\((?P<regname>[^()]+)\)"
                    m = re.search(pattern, line)
                    if m:
                        # new register found
                        if regname != None:
                            # okay, we found already other register
                            # save it
                            self.debug(f"LINE {line_num}: {line} ==== commit register {regname} {offset} {chapter} {page} {resetvalue} {bits}")
                            if bitstemp:
                                self.debug(f"LINE {line_num}: {line} ==== commit bitstemp {bitstemp}")
                                bits.append(bitstemp)
                            registers.append(
                                {
                                    "registername" : regname,
                                    "offset" : offset,
                                    "page" : page,
                                    "chapter" : chapter,
                                    "resetvalue": resetvalue,
                                    "bits" : bits,
                                }
                            )
                            # and reset our state
                            offset = None
                            resetvalue = None
                            bits = []
                            bitstemp = None
                            foundaddress = False
                            foundreset = False
                            foundbits = False

                        # load the new values from register line
                        chapter = m.group("chapter")
                        alternate = bool(m.group("alt"))
                        regname = m.group("regname")
                        if alternate:
                            # TODO
                            regname = regname + "-alternate"

                        page = self.page_nr
                        self.debug(f"LINE {line_num}: {line} ==== found register {regname} {chapter} {page}")

                    if foundaddress == False:
                        pattern = r"Address offset:\s*(0x[0-9A-Fa-f]+)"
                        m = re.search(pattern, line)
                        if m:
                            offset = m.group(1)
                            self.debug(f"LINE {line_num}: {line} ==== found offset {offset}")
                            foundaddress = True

                        oldline = line
                        continue

                    if foundreset == False:
                        pattern = r"Reset value:\s*(?P<resetvalue>0x[0-9A-Fa-fXx][0-9A-Fa-fXx_ ]*)"
                        m = re.search(pattern, line)
                        if m:
                            resetvalue = m.group("resetvalue")
                            hexpart = resetvalue[2:]
                            hexpart = hexpart.replace("_", "").replace(" ", "")
                            hexpart = hexpart.zfill(8)
                            resetvalue = "0x" + hexpart.lower()
                            self.debug(f"LINE {line_num}: {line} ==== found resetvalue {resetvalue}")
                            foundreset = True

                        oldline = line
                        continue

                    # at last, search bit descriptions
                    # LINE 25: Bit 31 RXFFIE: RXFIFO full interrupt enable
                    # LINE 26: This bit is set and cleared by software.
                    # LINE 27: 0: Interrupt inhibited
                    # LINE 28: 1: USART interrupt generated when RXFF=1 in the USART_ISR register
                    #
                    # LINE 29: Bit 30 TXFEIE: TXFIFO empty interrupt enable
                    #
                    # LINE 23: Bits 25:21 DEAT[4:0]: Driver enable assertion time
                    # 
                    # LINE 31: Bit 0 UE: USART enable
                    #
                    # LINE 16: Bits 31:17 Reserved, must be kept at reset value. True True True
                    #
                    # LINE 24: Bits 11:8 WKP[3:0]:
                    #
                    # LINE 14: Bits 31:0 OSPEEDR[15:0][1:0]: Port x configuration I/O pin y (y = 15 to 0)
                    #
                    pattern = re.compile(
                        r'^bits?\s+'
                        r'(?P<bit>\d{1,3}(?::\d{1,3})?)\s+'
                        r'(?P<bitname>[A-Za-z0-9_]+(?:\[[^\]]+\]){0,2})\s*'
                        r'[: ,]\s*'
                        r'(?P<description>.*)$',
                        flags=re.IGNORECASE
                    )
                    self.debug(f"LINE {line_num}: {line} ==== bits ====")
                    m = re.search(pattern, line)
                    if m:
                        if bitstemp:
                            self.debug(f"LINE {line_num}: {line} ==== commit bitstemp {bitstemp}")
                            bits.append(bitstemp)
                        
                        bitstemp = {
                                "range" : m.group("bit"),
                                "field" : m.group("bitname").strip(),
                                "description" : m.group("description").strip() + "\n",
                            }
                        self.debug(f"LINE {line_num}: {line} ==== set new bitstemp {bitstemp}")
                    else:
                        if bitstemp == None:
                            oldline = line
                            continue

                        bitstemp["description"] = bitstemp["description"] + line.strip() + "\n"
                        self.debug(f"LINE {line_num}: {line} ==== append bitstemp {bitstemp}")

                    oldline = line


    def create_register_maps(self, pdf):
        self.debug("==== create register maps ====")
        #self.debug(self.peripheralmaps)
        for regm in self.peripheralmaps:
            if regm['peripheral'] == "Reserved":
                continue

            if regm['peripheralmap'] == "-":
                continue

            self.debug(f"==== create register maps ==== {regm['peripheralmap']}")
            self.create_register_map(pdf, regm['peripheralmap'])

    def create_peripheral_map(self, pdf):
        # ['Bus', 'Boundary address', 'Size (Bytes)', 'Peripheral', 'Peripheral Register map']
        # ['Cortex-\nA7\ninternal', '0xA0026000 - 0xA0027FFF', '8KB', 'GICV', 'GIC virtual CPU interface (GICV)']
        # [None, '0xA0024000 - 0xA0025FFF', '8KB', 'GICH', 'GIC virtual interface control, common\n(GICH)']
        # [...] (Bus Always None until new bus
        # ['APB5', '0x5C00A400 - 0x5FFFFFFF', '65495KB', 'Reserved', '-']
        # [None, '0x5C00A000 - 0x5C00A3FF', '1KB', 'TAMP', 'TAMP registers']
        #
        # new page
        # ['Bus', 'Boundary address', 'Size (Bytes)', 'Peripheral', 'Peripheral Register map']
        # ['APB4', '0x5A007400 - 0x5BFFFFFF', '32739KB', 'Reserved', '-']
        # [None, '0x5A007000 - 0x5A0073FF', '1KB', 'DDRPERFM', 'DDRPERFM registers']
        #
        #  {
        #    "peripheralmap":"USART registers",  # from column Peripheral Register map
        #    "peripherial" : "USART2",           # from column Peripheral
        #    "range":"0x4000E000 - 0x4000E3FF",  # from column Boundary address
        #    "bus" : "APB1",                     # from column Bus
        #  },  
        self.bus = None
        for page_num in range(self.peripheralmapranges["start_page"] - 1, self.peripheralmapranges["end_page"]):
            self.page = pdf.pages[page_num]
            self.page_nr = page_num + 1
            #self.debug(f"\n=== Page {self.page_nr} === create_peripheral_map\n")
            #self.print_all_tables()
            tables = self.page.extract_tables()
            #self.debug(f"Tables page {self.page_nr} tables {tables}")
            for t_idx, table in enumerate(tables):
                #self.debug(f"\n--- Table {t_idx+1} ---")
                for row in table:
                    #self.debug(row)
                    if row[0] == "Bus":
                        continue
                    if row[0] != None:
                        self.bus = row[0].replace("\n", "")
                    self.peripheralmaps.append(
                        {
                            "bus" : self.bus,
                            "range" : row[1],
                            "size" : row[2],
                            "peripheral": row[3],
                            "peripheralmap" : row[4].replace("\n", ""),
                        }
                    )


    def handle_pdf(self, pdf):
        self.create_peripheral_map(pdf)
        self.create_register_maps(pdf)

    def convert(self):
        with pdfplumber.open(self.path + "/" + self.pdfname) as pdf:
            self.handle_pdf(pdf)

        result = {"peripheralmaps":self.peripheralmaps}, {"registermaps": self.registermaps}

        # save as JSON
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # debug("\n=== JSON result ===")
        # debug(json.dumps(result, indent=2, ensure_ascii=False))
        self.debug(f"Result saved as {self.output_file}")


def main():
    args = parse_arguments()

    regmap = pdf2json(args.soc)
    regmap.convert()


if __name__ == "__main__":
    main()
