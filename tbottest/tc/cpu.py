import tbot
from tbot.machine import linux
from tbot.context import Optional


@tbot.testcase
def board_lnx_cpufreq(
    lnx: Optional[linux.LinuxShell] = None,
    cpufreq=None,
) -> None:
    """
    simple cpufreq setup tests.

    look for all elements in cpufreq, if
    the file in "file" contains the value "val"

    :param lnx: linux machine we work on
    :param cpufreq: List of dictionary see below

    .. code-block:: python

        cpufreq = [
            {"file" : "/sys/devices/system/cpu/cpufreq/policy0/scaling_governor", "val" : "performance"},
            {"file" : "/sys/devices/system/cpu/cpufreq/policy0/cpuinfo_max_freq", "val" : "1600000"},
            {"file" : "/sys/devices/system/cpu/cpufreq/policy0/stats/time_in_state", "val" : "0"},
        ]
    """
    if cpufreq is None:
        raise RuntimeError("please configure cpufreq table")

    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        for c in cpufreq:
            out = lnx.exec0("cat", c["file"])
            if c["val"] not in out:
                raise RuntimeError(f'{c["val"]} not found in {c["file"]}')

@tbot.testcase
def generic_get_socname(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:
    """
    Try to find out the SoC name.

    First approach is to get name through /proc file
    /proc/device-tree/soc@0/compatible

    Currently supported SoC

    fsl,imx8mp-soc    -> NXP imx8mp -> return "imx8mp"

    :param lnx: linux machine where we run

    :return: see above table, if SoC could not be detected "not detected"
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        # Try through device-tree
        try:
            log = lnx.exec0("cat", "/proc/device-tree/soc@0/compatible")
            print("LOG ", log)
            if "fsl,imx8mp-soc" in log:
                return "imx8mp"
        except:
            pass

    return "not detected"
