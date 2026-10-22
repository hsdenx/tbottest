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

Currently supported SoCs:

- ```imx8mp```
- ```stm32mp157```

# stm32mp157 from the SVD file of ST

```stm32mp157_registers.json``` is made from the SVD file of ST, which has
every peripheral with its base address and every register with its bit
fields, and takes the bus of every peripheral and the descriptions and the
pages of the reference manual from the registermap the script
```stm32mp157_create_registermap.py``` made from the PDF, register by
register at the same address:

	wget -U "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)" https://www.st.com/resource/en/svd/stm32mp1-svd.zip
	unzip stm32mp1-svd.zip
	python3 stm32_svd_create_registermap.py -s STM32MP1_svd/STM32MP1_svd_v1.1/STM32MP157x.svd -m stm32mp157_registers.json --rm rm0436.pdf -o stm32mp157_registers.json

Most bit fields of the SVD have only their name as description. With
```--rm``` and the reference manual RM0436 (PDF, needs ```pdfplumber```),
```stm32_rm_descriptions.py``` looks every register up in the table of
contents of the PDF and takes page, chapter and the descriptions of the
fields from its section; they take the place of the ones of the SVD and of
```-m```. A field the reference manual names otherwise keeps what it has,
and a register it does not have (e.g. NVIC of the Cortex-M4) has no page
(```RM page None``` in the dump). The names of the registers are the ones
of the SVD, e.g. ```CR1``` for USART1, where the PDF has ```USART_CR1```.

# use the regdump tool without tbot

regdump.py needs neither tbot nor the installed tbottest, it takes
registermap.py from this repository.

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

Now cyclic addresses in documentation are also supported, example output:

	$ ./scripts/registermap/regdump.py -s imx8mp '[{"address":"0x30380800", "value":"0x00003210"}]'
	$ cat scripts/registermap/imx8mp_result.txt
	------------------------------------------------------------------------------
	register name: CCM_PLL_CTRLn val: 0x00003210 RM page 443
	------------------------------------------------------------------------------
	31-16  -                              val 0000000000000000
	desc This field is reserved.
	Reserved

	...........................................
	15     -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	14     -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	13-12  SETTING3                       val 11    
	desc Clock gate control setting for domain 3.
	This field can only be written by domain 3
	00 Domain clocks not needed
	01 Domain clocks needed when in RUN
	10 Domain clocks needed when in RUN and WAIT
	11 Domain clocks needed all the time

	...........................................
	11     -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	10     -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	9-8    SETTING2                       val 10    
	desc Clock gate control setting for domain 2.
	This field can only be written by domain 2
	00 Domain clocks not needed
	01 Domain clocks needed when in RUN
	10 Domain clocks needed when in RUN and WAIT
	11 Domain clocks needed all the time
	...........................................
	7      -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	6      -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	5-4    SETTING1                       val 01    
	desc Clock gate control setting for domain 1.
	This field can only be written by domain 1.
	00 Domain clocks not needed
	01 Domain clocks needed when in RUN
	10 Domain clocks needed when in RUN and WAIT
	11 Domain clocks needed all the time
	...........................................
	3      -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	2      -                              val 0     
	desc This field is reserved.
	Reserved

	...........................................
	NXPbug in doc name of field SETTING0 desc Clock gate control setting for domain 0.
	This field can only be written by domain 0.
	00 Domain clocks not needed
	01 Domain clocks needed when in RUN
	10 Domain clocks needed when in RUN and WAIT
	11 Domain clocks needed all the time
	...........................................

