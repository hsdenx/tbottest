import json
import tbot

from tbottest.tc.common_generic import get_bit_range


class REGISTERMAP:
    """
    helper class for creating register dumps with analysing
    the bits from a registermap.

    :param mapname: name of the registermap file

    registermap format is

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


    The registermap can for example contain register mappings
    from a SoC.

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

    def __init__(self, mapname: str) -> None:
        self.mapname = mapname
        self.registermap = None
        self.register_load_map()

    def register_load_map(self) -> bool:
        """
        load the register map and analyse it.
        """
        with open(self.mapname, "r", encoding="utf-8") as f:
            self.registermap = json.load(f)
            return True

        raise RuntimeError(f"Could not load register definitions from {self.mapname}")
        return None

    def registermap_search_address(self, address):
        """
        search for the address in the registermap

        :param address: hex string of address
        """
        for reg in self.registermap:
            if reg["address"] == address:
                return reg

        return None

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

        tbot.log.message(
            tbot.log.c(
                f"register name: {reg['register']} val: {val} RM page {reg['page']}"
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
