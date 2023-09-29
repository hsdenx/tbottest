import tbot

from tbotconfig.ci.testlab import laball
from tbotconfig.ci.testub import uball


@tbot.testcase
def all() -> str:  # noqa: D107
    """
    start all tests
    """
    laball()
    uball()
