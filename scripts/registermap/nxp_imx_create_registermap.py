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
        self.regmap = []
        self.current_register = None
        self.current_address = None
        self.current_bits = []
        self.current_bit = None
        self.current_page = None
        self.line_nr = None
        self.page_nr = None
        self.page = None
        self.found_new_register = False
        self.table_cont_next_page = False

        if self.soc == "imx8mp":
            self.pdfname = "IMX8MPRM.pdf"
            self.url = "https://www.nxp.com/webapp/Download?colCode=IMX8MPRM"
            self.ranges = [
                # ccm
                # {"start_page": 442, "end_page": 566},
                # gpc
                # {"start_page": 598, "end_page": 718},
                # otp
                # {"start_page": 833, "end_page": 868},
                # snvs
                # {"start_page": 877, "end_page": 897},
                # src
                # {"start_page": 909, "end_page": 968},
                # iomuxc
                {"start_page": 1361, "end_page": 1388},
                {"start_page": 1408, "end_page": 1982},
            ]
            # self.ranges = [
            #    # iomuxc
            #    {"start_page": 1361, "end_page": 1364},
            # ]
            self.output_file = f"{self.soc}_registers.json"
        else:
            raise RuntimeError(f"Soc {self.soc} not supported yet.")

    def debug(self, msg):
        print(msg)

    def is_field_name(self, line):
        line = line.replace("\n", "")

        self.debug(f"is_field_name {line}")
        if re.search(r"[A-Z_]", line) and not re.search(r"[a-z\-]", line):
            self.debug("is_field_name True")
            return True

        return False

    def extract_field_and_description(self, line):
        """
        extracts the filed name if there are only Uppercase letter or "_"
        and no Lowercase letters are in. The rest goes into the description
        """
        line = line.strip()
        # see problem5, some field names have "\n"
        line = line.replace("\n", "")
        self.debug(f"extract_field_and_description line {line}")
        if not line:
            return "", ""

        # Try to get the first word as a field name
        parts = line.split(maxsplit=1)
        candidate = parts[0]

        # check if there are Uppercase or "_" and no Lowercase
        if re.search(r"[A-Z_]", candidate) and not re.search(r"[a-z]", candidate):
            field_name = candidate
            description = parts[1].strip() if len(parts) > 1 else ""
        else:
            field_name = ""
            description = line

        self.debug(
            f"extract_field_and_description return field_name {field_name} description {description}"
        )
        return field_name, description

    def is_bitfield_line(self, line):
        """
        checks if it is a bitfiles

        - one number: 0,1,...
        - or a range: 31:28 oder 31–28
        """
        match = re.match(r"^(\d+[:–]?\d*)\s+", line)
        self.debug(f"is_bitfield {match}")
        if match:
            return match.group(1)

        return None

    def commit_register(self):
        if self.current_register is None:
            self.debug(
                f"commit current register do nothing current_register {self.current_register}"
            )
            return

        if self.current_bit:
            self.current_bits.append(self.current_bit)
            self.debug(
                f"[Page {self.page_nr} line {self.line_nr}] save last bitfiled: {self.current_bit}"
            )
            self.current_bit = None

        if self.current_register:
            self.debug(
                f"Commit Address {self.current_address} current_register {self.current_register}"
            )
            self.regmap.append(
                {
                    "register": self.current_register,
                    "address": self.current_address,
                    "page": self.current_page,
                    "bits": self.current_bits,
                }
            )
            self.debug(
                f"[Page {self.page_nr}] register {self.current_register} with {len(self.current_bits)} bitfields.\n"
            )

        self.found_new_register = False
        self.current_register = None

    def print_all_tables(self, page):
        tables = page.extract_tables()
        self.debug(f"\nfound tables: {len(tables)}")

        for t_idx, table in enumerate(tables):
            self.debug(f"\n--- Table {t_idx+1} ---")
            for row in table:
                self.debug(row)

    def get_table(self, page):
        self.print_all_tables(page)
        tables = page.extract_tables()
        for t_idx, table in enumerate(tables):
            fline = table[0]
            self.debug(
                f"table {t_idx} first '{fline[0]}' current_register {self.current_register} table_cont_next_page {self.table_cont_next_page}"
            )
            if self.table_cont_next_page:
                if f"{self.current_register} field descriptions (continued)" in fline:
                    self.debug(f"found continued {self.current_register} table")
                    return table
            if self.table_cont_next_page is False:
                if f"{self.current_register} field descriptions" in fline:
                    self.debug(f"found {self.current_register} table")
                    return table

        table = page.extract_table()
        self.debug(
            f"\n\nhandle table page: {self.page_nr} table {table} current_register {self.current_register}\n\n"
        )

        return table

    def handle_table(self):
        table = self.get_table(self.page)
        # we can have the following rows:
        # start of table
        # ['IOMUXC_GPR_GPR1 field descriptions', None]
        # continue on next page
        # ['IOMUXC_GPR_GPR1 field descriptions (continued)', None]
        # header
        # ['Field', 'Description']
        #
        # ['21\nIOMUXC_GPR_\nENET_QOS_\nRGMII_EN', 'ENET QOS TX clock direction select for RGMII or MII']
        # [None, '0 MII(input)\n1 RGMII(output)']
        # -> Bit 21 Field Name "IOMUXC_GPR_ENET_QOS_RGMII_EN"
        # -> Description: ENET QOS TX clock direction select for RGMII or MII
        #    continued in next row: 0 MII(input)\n1 RGMII(output)
        #
        # ['31–28\nGPR_DBG_\nACK_A53_MASK', 'Mask debug ack from each CA53 core']
        # [None, '0 unmasked\n1 mask to 0']
        #
        # ['Table continues on the next page...', None]
        #
        # problem lines
        # problem1
        # ['31–2\n-', 'This field is reserved.']
        # -> no field name, we replace "-" with reserved
        #
        # problem2
        # ['GPR_\nCORESIGHT_\nGPR_CTM_SEL', 'Select for Coresight master']
        # -> missing bitfields ! Grrrr, it should be 1-0
        #
        # problem3
        # ['-', 'This field is reserved.']
        # -> no field name, no bitfield
        #
        # problem4
        # ['', '011 ALT3_ISP_FL_TRIG_0 — Select mux mode: ALT3 mux port: ISP_FL_TRIG_0 of instance: isp\n101 ALT5_REF_CLK_32K — Select mux mode: ALT5 mux port: REF_CLK_32K of instance: anamix\n110 ALT6_CCM_EXT_CLK1 — Select mux mode: ALT6 mux port: CCM_EXT_CLK1 of instance: ccm']
        # -> field is ''
        #
        # problem5
        # ['GPC_IMR2_CORE0_A53 field descriptions', None]
        # ['Field', 'Description']
        # ['IMR2_CORE0_A\n53', 'A53 core0 IRQ[63:32] masking bits:']
        # [None, '0 IRQ not masked\n1 IRQ masked']
        # -> bitfiled has a "\n"
        #
        #
        if table:
            foundtable = False
            wascontinued = False
            for row in table:
                self.debug(
                    f"row {row} 0: {row[0]} 1: {row[1]} current_register {self.current_register}"
                )
                if f"{self.current_register} field descriptions" == row[0]:
                    self.debug(f"Found table {self.current_register}")
                    foundtable = True
                else:
                    if row[0] is not None:
                        if "field descriptions" in row[0]:
                            if (
                                f"{self.current_register} field descriptions (continued)"
                                == row[0]
                            ):
                                self.debug(
                                    f"Found continued table {self.current_register}"
                                )
                                if self.table_cont_next_page:
                                    foundtable = True
                                    self.table_cont_next_page = False
                                    wascontinued = True
                            else:
                                self.debug(
                                    f"Found table new? table {row[0]} current_register {self.current_register}"
                                )
                                self.table_cont_next_page = False
                                # only possible if we are already on a new page
                                if self.current_register:
                                    self.commit_register()
                                    return

                if foundtable is False:
                    continue

                if row[0] is not None:
                    if row[0] == "Field":
                        continue

                    if "Table continues on the next page" in row[0]:
                        self.debug(
                            f"Found continues on next page {self.current_register}"
                        )
                        self.table_cont_next_page = True
                        return

                    # debug(f"LINE {row[0]}")
                    bitrange = self.is_bitfield_line(row[0])
                    self.debug(f"bitrange: {bitrange}")
                    # NXP doc is buggy, some Field entries miss bitfield ...
                    # so try if we have a FIELD DESCRIPTION
                    field_name = ""
                    if self.is_field_name(row[0]):
                        self.debug(
                            f"bitrange {bitrange} wascontinued {wascontinued} row[1] {row[1]}"
                        )
                        if bitrange:
                            # replace the bitrange with "" so we get additional field name
                            row[0] = row[0].replace(bitrange, "", 1)
                            self.debug(f"fix row {row[0]}")
                        else:
                            if wascontinued and row[1] == "":
                                bitrange = False
                                self.debug(
                                    f"field_name empty, but continued current_bit {self.current_bit}"
                                )
                                if self.current_bit:
                                    self.current_bit["field"] = (
                                        self.current_bit["field"] + row[0]
                                    )
                                    self.current_bit["description"] = (
                                        self.current_bit["description"]
                                        + "\n"
                                        + row[1]
                                        + "\n"
                                    )
                            else:
                                self.debug(f"BUG not documented field_name {field_name}")
                                bitrange = "NXP bug not documented"

                        field_name = row[0].replace("\n", "")
                        if field_name == "MUX_MODE":
                            bitrange = "2-0"
                    elif row[0] == "-":
                        bitrange = "-"
                        field_name = "NXP bug -"
                        self.debug(f"BUG field_name {field_name}")
                    elif row[0] == "" and row[1] is not None:
                        bitrange = False
                        self.debug(f"field_name empty current_bit {self.current_bit}")
                        if self.current_bit:
                            self.current_bit["description"] = (
                                self.current_bit["description"] + "\n" + row[1] + "\n"
                            )

                    if bitrange:
                        if self.current_bit:
                            # if we have "\n"in field name, we safely can remove it
                            self.current_bit["field"] = self.current_bit["field"].replace(
                                "\n", ""
                            )
                            self.current_bits.append(self.current_bit)

                        if field_name == "":
                            field_name = row[0].split("\n")
                            self.debug(f"field_name '' {field_name}")
                            field_name = "".join(field_name[1:])
                        if row[1] == "This field is reserved." in row[1]:
                            field_name = "reserved"

                        description = row[1] + "\n"
                        self.current_bit = {
                            "range": bitrange.replace("–", "-"),
                            "field": field_name,
                            "description": description,
                        }
                else:
                    self.debug(f"row[0] == None row[1] {row[1]}")
                    if self.current_bit is None:
                        raise RuntimeError(
                            "found row with None, but no current_bit set before"
                        )

                    description = self.current_bit["description"]
                    self.debug(f"old description {description}")
                    description += row[1]
                    self.current_bit["description"] = description

            if foundtable:
                self.commit_register()

        else:
            raise RuntimeError("Keine Tabelle gefunden auf Seite", self.page_nr)

    def one_line(self, line):
        self.debug(f"one line {self.page} nr {self.page_nr}")
        line = line.strip()
        if not line:
            return

        # Debug: Ausgabe der aktuellen Zeile
        self.debug(f"LINE {self.line_nr} cbit {self.current_bit}: {line}")

        # Register erkennen
        reg_match = re.search(r"([A-Z0-9_]+)\s+field descriptions", line)
        if reg_match:
            tmpname = reg_match.group(1)
            if self.current_register == tmpname:
                self.debug(f"found register {tmpname} already open")
                return
            if "continued" in line:
                self.debug(
                    f"found new register continued current_register {self.current_register} tmpname {tmpname}"
                )
                print("This is a bug")
                print(
                    "calling the table did not find the IOMUXC_GPR_GPR1 field descriptions (continued) table...."
                )
                print("In the pdf there is the table ...")
                return
            else:
                self.debug(f"found new register {tmpname}")
                self.commit_register()

            if self.current_register is None:
                self.current_register = tmpname
                self.current_page = self.page_nr
                self.current_bits = []
                self.current_bit = None
                self.debug(
                    f"[Page {self.page_nr} line {self.line_nr}] found registername: {self.current_register}"
                )
                self.found_new_register = True
                if self.table_cont_next_page:
                    self.table_cont_next_page = False

                return

        # detect Address
        addr_match = re.search(r"Address: (\S+)", line)
        if addr_match:
            addr = line.split("=")
            addr = addr[1].strip()
            addr = addr.replace("_", "")
            if addr[-1] == "h":
                addr = "0x" + addr[:-1]

            self.current_address = addr.replace("_", "")
            self.debug(
                f"[Page {self.page_nr} Line {self.line_nr}] found address: {self.current_address}"
            )
            return

        # table handling
        if self.found_new_register:
            self.handle_table()

    def handle_pdf(self, pdf, start_page, end_page):
        for page_num in range(start_page - 1, end_page):  # pdfplumber indexiert ab 0
            self.page = pdf.pages[page_num]

            self.page_nr = page_num + 1
            self.debug(f"\n=== Page {self.page_nr} ===\n")
            if self.table_cont_next_page:
                self.debug("continue table on next page")
                self.handle_table()
                if self.table_cont_next_page:
                    self.debug("table needed complete page")
                    continue

            self.debug(f"\n=== Page {self.page_nr} start with analysing text ===\n")

            text = self.page.extract_text()
            if text:
                lines = text.split("\n")
                for line_num, line in enumerate(lines, start=1):
                    self.line_nr = line_num
                    self.one_line(line)
                    self.debug(
                        f"[Page {self.page_nr} Line {line_num}] {line} table_cont_next_page {self.table_cont_next_page}"
                    )
                    if self.table_cont_next_page:
                        break
            else:
                self.debug(f"No textlines on {self.page_nr} found")

        # save last register
        if self.current_register:
            if self.current_bit:
                self.current_bits.append(self.current_bit)
                self.debug(
                    f"[Page {self.current_page}] save last register bitfiled: {self.current_bit}"
                )

            self.debug(f"last Commit Address {self.current_address}")
            self.regmap.append(
                {
                    "register": self.current_register,
                    "address": self.current_address,
                    "page": self.current_page,
                    "bits": self.current_bits,
                }
            )
            self.debug(
                f"[Page {self.current_page}] register {self.current_register} with {len(self.current_bits)} bitfields saved.\n"
            )

    def convert(self):
        with pdfplumber.open(self.pdfname) as pdf:
            for r in self.ranges:
                self.handle_pdf(pdf, r["start_page"], r["end_page"])

        # save as JSON
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(self.regmap, f, indent=2, ensure_ascii=False)

        # debug("\n=== JSON result ===")
        # debug(json.dumps(regmap, indent=2, ensure_ascii=False))
        self.debug(f"Result saved as {self.output_file}")


def main():
    args = parse_arguments()

    regmap = pdf2json(args.soc)
    regmap.convert()


if __name__ == "__main__":
    main()
