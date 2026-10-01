"""
Interactive access to an Abatron BDI2000 debugger.

The debugger is set up per board in tbot.ini::

    [BDI2000_<boardname>]
    ip = 192.168.3.101

and reached with telnet from the lab host, through the BDI2000 machine
from tbottest.bdi2000.
"""
import tbot

from tbottest.bdi2000 import BDI2000


@tbot.testcase
def bdi2000() -> None:
    """
    Open an interactive session on the board's BDI2000 command line.

    Leave it like any other interactive session, with CTRL+] three times
    within one second.
    """
    with tbot.ctx.request(BDI2000) as bdi:
        bdi.interactive()
