import pdfplumber
import re
import json

output_file = "imx8mp_registers.json"
pdf_path = "IMX8MPRM.pdf"

ranges = [
    # iomuxc
    {"start_page": 1361, "end_page": 1388},
    {"start_page": 1408, "end_page": 1982},
]

imx8mp = []
current_register = None
current_address = None
current_bits = []
current_bit = None
current_page = None
line_nr = None
page_nr = None
page = None
found_new_register = False
table_cont_next_page = False


def debug(msg):
    print(msg)


def is_field_name(line):
    line = line.replace("\n", "")

    if re.search(r"[A-Z_]", line) and not re.search(r"[a-z0-9\-]", line):
        return True

    return False


def extract_field_and_description(line):
    """
    extracts the filed name if there are only Uppercase letter or "_"
    and no Lowercase letters are in. The rest goes into the description
    """
    line = line.strip()
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

    return field_name, description


def is_bitfield_line(line):
    """
    checks if it is a bitfiles

    - one number: 0,1,...
    - or a range: 31:28 oder 31–28
    """
    match = re.match(r"^(\d+[:–]?\d*)\s+", line)
    debug(f"is_bitfield {match}")
    if match:
        return match.group(1)

    return None


def commit_register():
    global imx8mp
    global current_bit
    global current_bits
    global current_page
    global current_address
    global current_register
    global page
    global page_nr
    global line_nr
    global table_cont_next_page
    global found_new_register

    if current_register is None:
        debug(f"commit current register do nothing current_register {current_register}")
        return

    if current_bit:
        current_bits.append(current_bit)
        debug(
            f"[Seite {page_nr} Zeile {line_nr}] Letztes Bitfeld des Registers gespeichert: {current_bit}"
        )
        current_bit = None

    if current_register:
        debug(f"Commit Address {current_address} current_register {current_register}")
        imx8mp.append(
            {
                "register": current_register,
                "address": current_address,
                "page": current_page,
                "bits": current_bits,
            }
        )
        debug(
            f"[Seite {page_nr}] Register {current_register} mit {len(current_bits)} Bitfeldern gespeichert.\n"
        )

    found_new_register = False
    current_register = None


def print_all_tables(page):
    tables = page.extract_tables()
    print(f"\nGefundene Tabellen: {len(tables)}")

    for t_idx, table in enumerate(tables):
        print(f"\n--- Tabelle {t_idx+1} ---")
        for row in table:
            print(row)


def get_table(page):
    global current_page
    global page_nr
    global current_register
    global table_cont_next_page

    print_all_tables(page)
    tables = page.extract_tables()
    for t_idx, table in enumerate(tables):
        fline = table[0]
        debug(
            f"table {t_idx} first '{fline[0]}' current_register {current_register} table_cont_next_page {table_cont_next_page}"
        )
        if table_cont_next_page:
            if f"{current_register} field descriptions (continued)" in fline:
                debug(f"found continued {current_register} table")
                return table
        if table_cont_next_page is False:
            if f"{current_register} field descriptions" in fline:
                debug(f"found {current_register} table")
                return table

    table = page.extract_table()
    debug(
        f"\n\nhandle table page: {page_nr} table {table} current_register {current_register}\n\n"
    )

    return table


def handle_table():
    global current_bit
    global current_bits
    global current_page
    global current_address
    global current_register
    global page
    global table_cont_next_page

    table = get_table(page)
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
    # ['31–2\n-', 'This field is reserved.']
    # -> no field name, we replace "-" with reserved
    #
    # ['GPR_\nCORESIGHT_\nGPR_CTM_SEL', 'Select for Coresight master']
    # -> missing bitfields ! Grrrr, it should be 1-0
    #
    # ['-', 'This field is reserved.']
    # -> no field name, no bitfield
    #
    # ['', '011 ALT3_ISP_FL_TRIG_0 — Select mux mode: ALT3 mux port: ISP_FL_TRIG_0 of instance: isp\n101 ALT5_REF_CLK_32K — Select mux mode: ALT5 mux port: REF_CLK_32K of instance: anamix\n110 ALT6_CCM_EXT_CLK1 — Select mux mode: ALT6 mux port: CCM_EXT_CLK1 of instance: ccm']
    # -> field is ''
    #
    if table:
        foundtable = False
        for row in table:
            debug(
                f"row {row} 0: {row[0]} 1: {row[1]} current_register {current_register}"
            )
            if f"{current_register} field descriptions" == row[0]:
                debug(f"Found table {current_register}")
                foundtable = True
            else:
                if row[0] is not None:
                    if "field descriptions" in row[0]:
                        if f"{current_register} field descriptions (continued)" == row[0]:
                            debug(f"Found continued table {current_register}")
                            if table_cont_next_page:
                                foundtable = True
                                table_cont_next_page = False
                        else:
                            debug(
                                f"Found table new? table {row[0]} current_register {current_register}"
                            )
                            table_cont_next_page = False
                            # only possible if we are already on a new page
                            if current_register:
                                commit_register()
                                return

            if foundtable is False:
                continue

            if row[0] is not None:
                if row[0] == "Field":
                    continue

                if "Table continues on the next page" in row[0]:
                    debug(f"Found continues on next page {current_register}")
                    table_cont_next_page = True
                    return

                # debug(f"LINE {row[0]}")
                # field_name, description = extract_field_and_description(row[0])
                # debug(f"field: {field_name} desc: {description}")
                range = is_bitfield_line(row[0])
                debug(f"range: {range}")
                # NXP doc is buggy, some Field entries miss bitfield ...
                # so try if we have a FIELD DESCRIPTION
                field_name = ""
                if is_field_name(row[0]):
                    field_name = row[0].replace("\n", "")
                    debug(f"BUG not documented field_name {field_name}")
                    range = "NXP bug not documented"
                    if field_name == "MUX_MODE":
                        range = "2-0"
                if row[0] == "-":
                    range = "-"
                    field_name = "NXP bug -"
                    debug(f"BUG field_name {field_name}")
                if row[0] == "" and row[1] is not None:
                    range = False
                    debug(f"field_name empty current_bit {current_bit}")
                    if current_bit:
                        current_bit["description"] = (
                            current_bit["description"] + "\n" + row[1] + "\n"
                        )
                if range:
                    if current_bit:
                        current_bits.append(current_bit)

                    if field_name == "":
                        field_name = row[0].split("\n")
                        debug(f"field_name '' {field_name}")
                        field_name = "".join(field_name[1:])
                    if row[1] == "This field is reserved." in row[1]:
                        field_name = "reserved"

                    description = row[1] + "\n"
                    current_bit = {
                        "range": range.replace("–", "-"),
                        "field": field_name,
                        "description": description,
                    }
            else:
                debug(f"row[0] == None row[1] {row[1]}")
                if current_bit is None:
                    raise RuntimeError(
                        "found row with None, but no current_bit set before"
                    )

                description = current_bit["description"]
                debug(f"old description {description}")
                description += row[1]
                current_bit["description"] = description

        if foundtable:
            commit_register()

    else:
        raise RuntimeError("Keine Tabelle gefunden auf Seite", page_nr)


def one_line(line):
    global imx8mp
    global current_bit
    global current_bits
    global current_page
    global current_address
    global current_register
    global line_nr
    global page
    global page_nr
    global found_new_register
    global table_cont_next_page

    debug(f"one line {page} nr {page_nr}")
    line = line.strip()
    if not line:
        return

    # Debug: Ausgabe der aktuellen Zeile
    debug(f"LINE {line_nr} cbit {current_bit}: {line}")

    # Register erkennen
    reg_match = re.search(r"([A-Z0-9_]+)\s+field descriptions", line)
    if reg_match:
        tmpname = reg_match.group(1)
        if current_register == tmpname:
            debug(f"found register {tmpname} already open")
            return
        if "continued" in line:
            debug(
                f"found new register continued current_register {current_register} tmpname {tmpname}"
            )
            print("This is a bug")
            print(
                "calling the table did not find the IOMUXC_GPR_GPR1 field descriptions (continued) table...."
            )
            print("In the pdf there is the table ...")
            return
        else:
            debug(f"found new register {tmpname}")
            commit_register()

        if current_register is None:
            current_register = tmpname
            current_page = page_nr
            current_bits = []
            current_bit = None
            debug(
                f"[Page {page_nr} line {line_nr}] found registername: {current_register}"
            )
            found_new_register = True
            if table_cont_next_page:
                table_cont_next_page = False

            return

    # detect Address
    addr_match = re.search(r"Address: (\S+)", line)
    if addr_match:
        addr = line.split("=")
        addr = addr[1].strip()
        addr = addr.replace("_", "")
        if addr[-1] == "h":
            addr = "0x" + addr[:-1]

        current_address = addr.replace("_", "")
        debug(f"[Page {page_nr} Line {line_nr}] found address: {current_address}")
        return

    # table handling
    if found_new_register:
        handle_table()


def handle_pdf(pdf, start_page, end_page):
    global imx8mp
    global current_bit
    global current_bits
    global current_page
    global current_address
    global current_register
    global line_nr
    global page
    global page_nr
    global found_new_register
    global table_cont_next_page

    for page_num in range(start_page - 1, end_page):  # pdfplumber indexiert ab 0
        page = pdf.pages[page_num]

        page_nr = page_num + 1
        debug(f"\n=== Page {page_nr} ===\n")
        if table_cont_next_page:
            debug("continue table on next page")
            handle_table()
            if table_cont_next_page:
                debug("table needed complete page")
                continue

        debug(f"\n=== Page {page_nr} start with analysing text ===\n")

        text = page.extract_text()
        if text:
            lines = text.split("\n")
            for line_num, line in enumerate(lines, start=1):
                line_nr = line_num
                one_line(line)
                debug(
                    f"[Page {page_nr} Line {line_num}] {line} table_cont_next_page {table_cont_next_page}"
                )
                if table_cont_next_page:
                    break
        else:
            debug(f"No textlines on {page_nr} found")

    # save last register
    if current_register:
        if current_bit:
            current_bits.append(current_bit)
            debug(f"[Page {current_page}] save last register bitfiled: {current_bit}")

        debug(f"last Commit Address {current_address}")
        imx8mp.append(
            {
                "register": current_register,
                "address": current_address,
                "page": current_page,
                "bits": current_bits,
            }
        )
        debug(
            f"[Page {current_page}] register {current_register} with {len(current_bits)} bitfields saved.\n"
        )

    # save as JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(imx8mp, f, indent=2, ensure_ascii=False)

    # debug("\n=== JSON result ===")
    # debug(json.dumps(imx8mp, indent=2, ensure_ascii=False))
    debug(f"Result saved as {output_file}")


with pdfplumber.open(pdf_path) as pdf:
    for r in ranges:
        handle_pdf(pdf, r["start_page"], r["end_page"])
