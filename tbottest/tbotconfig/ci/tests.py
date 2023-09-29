import tbot

from tbotconfig.ci.testlab import laball
from tbotconfig.ci.testub import uball
from tbotconfig.ci.testlnx import lnxall
from tbotconfig.ci.testbh import bhall


@tbot.testcase
def all() -> str:  # noqa: D107
    """
    start all tests
    """
    laball()
    uball()
    lnxall()
    bhall()
