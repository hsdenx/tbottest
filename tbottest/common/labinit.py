"""
Lab host initialisation, done once per boot of the lab host.

Two markers below /tmp on the lab host record what has been done:

* LABINIT_MARKER for the labinit commands of the [LABHOST] section, which
  belong to the lab host,
* LABINIT_MARKER-<boardname> for the setup of the board's ethernet devices
  on the lab host, which differ from board to board.

A marker is written only after its part succeeded, so a failing command is
tried again on the next run.
"""
import ast
import time

import tbot
from tbot.machine import linux

LABINIT_MARKER = "/tmp/tbotlabinitdone"


def labinit_from_config(config_parser, section: str) -> list:
    """
    returns the list of labinit commands from section, or an empty list
    if the entry is missing or not a valid python list
    """
    try:
        return list(ast.literal_eval(config_parser.get(section, "labinit")))
    except Exception:
        return []


def lab_init_once(
    lab, labinit: list, boardname: str, ethdevices: dict, ethinit: bool = True
) -> None:
    """
    run the labinit commands and set up the board's ethernet devices on
    the lab host, each only if its marker does not exist yet

    :param lab: lab host
    :param labinit: commands to run on the lab host
    :param boardname: name of the board, part of the ethernet marker
    :param ethdevices: the board's ethernet devices, each a dict with
        labdevice and serverip
    :param ethinit: False skips the ethernet setup (flag noethinit)
    """
    ret, _ = lab.exec("test", "-f", LABINIT_MARKER)
    if ret != 0:
        for cmd in labinit:
            lab.exec0(linux.Raw(cmd))

        lab.exec0("date", linux.Raw(">"), LABINIT_MARKER)

    if not ethinit:
        return

    ethmarker = f"{LABINIT_MARKER}-{boardname}"
    ret, _ = lab.exec("test", "-f", ethmarker)
    if ret == 0:
        return

    # imported here, so this module stays importable without the board
    # environment that tbottest.tc pulls in
    from tbottest.tc.network import lnx_has_netdev, lnx_set_ipaddr

    for ethdev in ethdevices.values():
        labdev = ethdev["labdevice"]
        if not lnx_has_netdev(lab, labdev):
            tbot.log.message(
                tbot.log.c(f"ethernet device {labdev} not found on lab host").yellow
            )
            continue

        # without netmask, as before: the prefix follows the address class
        lnx_set_ipaddr(lab, labdev, ethdev["serverip"], sudo=True)
        out = lab.exec0("ip", "link", "show", "dev", labdev)
        while "NO-CARRIER" in out:
            lab.exec0("sudo", "ethtool", "-s", labdev, "autoneg", "on")
            time.sleep(1)
            out = lab.exec0("ip", "link", "show", "dev", labdev)

    lab.exec0("date", linux.Raw(">"), ethmarker)
