import json
from pathlib import Path

try:
    import tbot
except:
    print("tbot lib not found, some functions will fail")
    pass

from tbottest.tc.common_generic import get_bit_range


class REGISTERMAP:
    """
    helper class for creating register dumps with analysing
    the bits from a registermap.

    :param mapname: name of the registermap file

    registermap format for NXP is

    .. code-block:: python

        [
          {
            "register": "name of the register",
            "address": "address in hex of the regsiter",
            "page": <page in the reference manual>,
            "bits": [
              {
                "range": "bitfiles range example '3' '31-27' ",
                "field": "name of the bitfield",
                "description": "help text from the manuel for the field"
              }
            ]
          },
        ]

    registermap format for STM32MP157 is

    .. code-block:: python

        [
          {
            "peripheralmaps": [
              {
                "bus": "Cortex-A7internal",
                "range": "0xA0026000 - 0xA0027FFF",
                "size": "8KB",
                "peripheral": "GICV",
                "peripheralmap": "GIC virtual CPU interface (GICV)"
              },
            ]
          },
          {
            "registermaps": [
              {
                "mapname": "I2C registers",
                "registers": [
                  {
                    "registername": "I2C_CR1",
                    "offset": "0x00",
                    "page": 2559,
                    "chapter": "52.9.1",
                    "resetvalue": "0x00000000",
                    "bits": [
                              {
                                "range": "31:24",
                                "field": "Reserved",
                                "description": "must be kept at reset value.\n"
                              },
                    ]
                  },
                ]
              },
            ]
          }
        ]


    The registermap contain register mappings for a SoC.

    Example for imx8mp:

    .. code-block:: python

        from tbottest.tc.uboot import ub_read_register
        from tbottest.tc.registermap import REGISTERMAP

        regmap = REGISTERMAP("imx8mp_registers.json")
        with tbot.ctx() as cx:
            if ub is None:
                ub = cx.request(tbot.role.BoardUBoot)

            addresses = ["0x30330070"]
            for address in addresses:
                val = ub_read_register(ub, address)
                regmap.registermap_dump_register(address, val)

    Will generate the following register dump

    .. code-block:: shell

        │   ├─[helios-uboot] md.l 0x30330070 1
        │   │    ## 30330070: 00000000                             ....
        │   ├─-------------------------------
        │   ├─register name: IOMUXC_SW_MUX_CTL_PAD_ENET_TXC val: 0x00000000 RM page 1438
        │   ├─31-5   -                              val 000000000000000000000000000
        │   ├─desc This field is reserved.
        │   │ Reserved
        │   │
        │   ├─--------
        │   ├─4      SION                           val 0
        │   ├─desc Software Input On Field.
        │   │ Force the selected mux mode Input path no matter of MUX_MODE functionality.
        │   │ 1 ENABLED — Force input path of pad ENET_TXC
        │   │ 0 DISABLED — Input Path is determined by functionality
        │   ├─--------
        │   ├─3      -                              val 0
        │   ├─desc This field is reserved.
        │   │ Reserved
        │   │
        │   ├─--------
        │   ├─2-0    MUX_MODE                       val 000
        │   ├─desc MUX Mode Select Field.
        │   │ Select 1 of 6 iomux modes to be used for pad: ENET_TXC.
        │   │ 000 ALT0_CCM_ENET_QOS_CLOCK_GENERATE_TX_CLK — Select mux mode: ALT0 mux port:
        │   │ CCM_ENET_QOS_CLOCK_GENERATE_TX_CLK of instance: ccm_enet_qos_clock_generate
        │   │ 001 ALT1_ENET_QOS_TX_ER — Select mux mode: ALT1 mux port: ENET_QOS_TX_ER of instance:
        │   │ enet_qos
        │   │ 010 ALT2_AUDIOMIX_SAI7_TX_DATA[0] — Select mux mode: ALT2 mux port:
        │   │ AUDIOMIX_SAI7_TX_DATA00 of instance: sai7
        │   │ 101 ALT5_GPIO1_IO[23] — Select mux mode: ALT5 mux port: GPIO1_IO23 of instance: gpio1
        │   │ 110 ALT6_USDHC3_DATA1 — Select mux mode: ALT6 mux port: USDHC3_DATA1 of instance:
        │   │ usdhc3
        │   │
        │   ├─--------


    There are also helper script in `scripts/registermap <https://github.com/hsdenx/tbottest/tree/master/scripts/registermap>`_
    with which you can generate such a mapping from a reference manual.

    """

    def __init__(self, mapname: str, socname: str = None) -> None:
        self.mapname = mapname
        if socname == None:
            # Try to get socname from filename
            self.socname = Path(self.mapname).name
            self.socname = self.socname.split("_")[0]

        self.registermap = None
        self.register_load_map()

    def get_registername_from_dict(self) -> str:
        """
        return the name of the registername field in the
        dictionary for the SoC.
        """
        if self.socname == "imx8mp":
            return "register"
        elif self.socname == "stm32mp157":
            return "registername"

        raise RuntimeError(f"register field name in dict for SoC {self.socname} not found")

    def register_load_map(self) -> bool:
        """
        load the register map and analyse it.
        """
        with open(self.mapname, "r", encoding="utf-8") as f:
            self.registermap = json.load(f)
            return True

        raise RuntimeError(f"Could not load register definitions from {self.mapname}")
        return None

    def registermap_nxp_search_address(self, address):
        """
        search for the address in the imx8mp registermap

        :param address: hex string of address
        """
        for reg in self.registermap:
            if reg["address"]:
                if reg["address"] == address:
                    return reg
            elif reg["address_cyclic"]:
                tmp = reg["address_cyclic"]
                base = tmp["base"]
                off = tmp["offset"]
                step = tmp["step"]
                start = tmp["start"]
                end = tmp["end"]

                addr = int(base, 16)
                offset = int(off, 16)
                valid_addresses = [
                    addr + offset + step * i for i in range(start, end + 1)
                ]

                tmp = int(address, 16)
                if tmp in valid_addresses:
                    return reg

        return None

    def registermap_stm32mp1_search_address(self, address):
        """
        search for the address in the imx8mp registermap

        :param address: hex string of address
        """
        permaps = self.registermap[0]['peripheralmaps']
        regmaps = self.registermap[1]['registermaps']
        tmpaddr = int(address, 16)

        # search peripheral mapping
        permap = None
        startaddr = None
        for p in permaps:
            start_str, end_str = p["range"].split(" - ")
            start = int(start_str, 16)
            end = int(end_str, 16)
            if tmpaddr >= start and tmpaddr <= end:
                permap = p
                startaddr = start
                break

        if not permap:
            raise RuntimeError(f"No peripheral map found for address {address}")

        # search registermap
        regmap = None
        for r in regmaps:
            if r["mapname"] == permap["peripheralmap"]:
                regmap = r
                break

        if not regmap:
            raise RuntimeError(f"No registermap map found for address {address}")

        # find registermapping for full address
        for reg in regmap["registers"]:
            registeraddr = startaddr + int(reg["offset"], 16)
            if registeraddr == tmpaddr:
                return reg

        raise RuntimeError(f"address {address} not found")

    def registermap_search_address(self, address):
        """
        search for the address in the registermap for the SoC

        :param address: hex string of address
        """
        if self.socname == "imx8mp":
            return self.registermap_nxp_search_address(address)
        elif self.socname == "stm32mp157":
            return self.registermap_stm32mp1_search_address(address)

        raise RuntimeError(f"Soc {self.socname} not yet supported")


    def registermap_dump_register(self, address, val) -> bool:
        """
        dump the value val which is read from address

        This is a first proofe of concept version, the output
        could be nicer.

        :param address: hex string of address
        :param val: value hex_string
        """
        tbot.log.message("-------------------------------")
        reg = self.registermap_search_address(address)
        if reg is None:
            tbot.log.message(tbot.log.c(f"regitermapping for {address} not found").red)
            return False

        regname = self.get_registername_from_dict()
        tbot.log.message(
            tbot.log.c(
                f"register name: {reg[regname]} val: {val} RM page {reg['page']}"
            ).blue
        )
        for bit in reg["bits"]:
            if "NXP bug not documented" in bit["range"]:
                tbot.log.message(
                    tbot.log.c(
                        f"NXPbug in doc name of field {bit['field']} desc {bit['description']}"
                    ).red
                )
            elif bit["range"] == "-":
                tbot.log.message(
                    tbot.log.c(f"field {bit['field']} desc {bit['description']}").red
                )
            else:
                bits = get_bit_range(val, bit["range"])
                tbot.log.message(
                    tbot.log.c(f"{bit['range']:6} {bit['field']:30} val {bits:6}").blue
                )
                tbot.log.message(f"desc {bit['description']}")
            tbot.log.message("--------")

        return True

    def registermap_dump_register_file(self, filepath, address, val) -> bool:
        """
        dump the value val which is read from address into a file

        This is a first proofe of concept version, the output
        could be nicer.

        :param filepath: full path to outputfile
        :param address: hex string of address
        :param val: value hex_string

        Example output:

        .. code-block:: shell

            ------------------------------------------------------------------------------
            register name: IOMUXC_SW_MUX_CTL_PAD_ENET_TXC val: 0x00000000 RM page 1438
            ------------------------------------------------------------------------------
            31-5   -                              val 000000000000000000000000000
            desc This field is reserved.
            Reserved

            ...........................................
            4      SION                           val 0
            desc Software Input On Field.
            Force the selected mux mode Input path no matter of MUX_MODE functionality.
            1 ENABLED — Force input path of pad ENET_TXC
            0 DISABLED — Input Path is determined by functionality
            ...........................................
            3      -                              val 0
            desc This field is reserved.
            Reserved

            ...........................................
            2-0    MUX_MODE                       val 000
            desc MUX Mode Select Field.
            Select 1 of 6 iomux modes to be used for pad: ENET_TXC.
            000 ALT0_CCM_ENET_QOS_CLOCK_GENERATE_TX_CLK — Select mux mode: ALT0 mux port:
            CCM_ENET_QOS_CLOCK_GENERATE_TX_CLK of instance: ccm_enet_qos_clock_generate
            001 ALT1_ENET_QOS_TX_ER — Select mux mode: ALT1 mux port: ENET_QOS_TX_ER of instance:
            enet_qos
            010 ALT2_AUDIOMIX_SAI7_TX_DATA[0] — Select mux mode: ALT2 mux port:
            AUDIOMIX_SAI7_TX_DATA00 of instance: sai7
            101 ALT5_GPIO1_IO[23] — Select mux mode: ALT5 mux port: GPIO1_IO23 of instance: gpio1
            110 ALT6_USDHC3_DATA1 — Select mux mode: ALT6 mux port: USDHC3_DATA1 of instance:
            usdhc3



        """
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(
                "------------------------------------------------------------------------------\n"
            )
            reg = self.registermap_search_address(address)
            if reg is None:
                f.write(f"registermapping for {address} not found\n")
                return False

            regname = self.get_registername_from_dict()
            f.write(
                f"register name: {reg[regname]} val: {val} RM page {reg['page']}\n"
            )
            f.write(
                "------------------------------------------------------------------------------\n"
            )
            for bit in reg["bits"]:
                if "NXP bug not documented" in bit["range"]:
                    f.write(
                        f"NXPbug in doc name of field {bit['field']} desc {bit['description']}\n"
                    )
                elif bit["range"] == "-":
                    f.write(f"field {bit['field']} desc {bit['description']}\n")
                else:
                    bits = get_bit_range(val, bit["range"])
                    f.write(f"{bit['range']:6} {bit['field']:30} val {bits:6}\n")
                    f.write(f"desc {bit['description']}\n")
                f.write("...........................................\n")

        return True
