# create a registermapping

copy the imx8mp reference manual ```IMX8MPRM.pdf```
into the path where you have this script and call it with

    python3 nxp_imx_create_registermap.py -s imx8mp

This will generate the registermap file ```imx8mp_registers.json```
you than can use with the class REGISTERMAP

The script currently creates a registermap for the following
registers:

    ranges = [
        # iomuxc
        {"start_page":1361, "end_page":1388},
        {"start_page":1408, "end_page":1982},
    ]

If you need others, adapt the script or send patches, which
makes this more comfortable.

Currently there is only SoC ```imx8mp``` supported.

# use the regdump tool without tbot

clone this repo

	git clone https://github.com/hsdenx/tbottest.git
	cd tbottest

and start the script. Example:

	$ scripts/registermap/regdump.py -s imx8mp '[{"address":"0x30330070", "value":"0x00000000"}, {"address":"0x30340004", "value":"0x00690000"}]'

you now should find the result in ```scripts/registermap/imx8mp_result.txt```

Example output from

	$ scripts/registermap/regdump.py -s imx8mp '[{"address":"0x30330070", "value":"0x00000000"}]'
	$ cat scripts/registermap/imx8mp_result.txt
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

	...........................................
