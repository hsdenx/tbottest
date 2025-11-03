# create imx8mp registermapping

copy the imx8mp reference manual ```IMX8MPRM.pdf```
into the path where you have this script and call it with

    python3 nxp_imx_create_registermap.py

This will generate the registermap file ```imx8mp_registers.json```
you than can use with the class REGISTERMAP

The script currently creates a registermap for the following
registers:

    ranges = [
        # iomuxc
        {"start_page":1361, "end_page":1388},
        {"start_page":1408, "end_page":1982},
    ]

f you need others, adapt the script or send patches, which
makes this more comfortable.

You find the resulting ouput also in this directory.
