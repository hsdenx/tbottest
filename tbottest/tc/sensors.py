#
# collection of testcases for sensor testing
# may go into mainline
#
import tbot
from tbot.machine import linux
from tbot.context import Optional


@tbot.testcase
def board_lnx_tempsensors(
    lnx: Optional[linux.LinuxShell] = None, sensors=None,
) -> None:
    """
    prerequisite: Board boots into linux

    test temp sensors

    :param lnx: linux machine where we work on
    :param sensors: List of dictionary, see below

    .. code-block:: python

        sensors = [{"path":"full path to sensor", "name":"name of the sensor", "tmpvalues":[{"valname":"name of the sensor value", "min":"minimal allowed value", "max":"maximal allowed value"}]}]

        sensors = [
            {"path" : "/sys/bus/i2c/drivers/tmp102/0-0048/hwmon/hwmon0", "name" : "tmp102", "tmpvalues" : [{"valname" : "temp1_input", "min" : "0", "max" : "100000"}]},
            {"path" : "/sys/bus/i2c/drivers/tmp102/0-0049/hwmon/hwmon1", "name" : "tmp102", "tmpvalues" : [{"valname" : "temp1_input", "min" : "0", "max" : "100000"}]},
            {"path" : "/sys/bus/i2c/drivers/tmp102/0-004a/hwmon/hwmon2", "name" : "tmp102", "tmpvalues" : [{"valname" : "temp1_input", "min" : "0", "max" : "100000"}]},
            {"path" : "/sys/bus/i2c/drivers/tmp102/0-004b/hwmon/hwmon3", "name" : "tmp102", "tmpvalues" : [{"valname" : "temp1_input", "min" : "0", "max" : "100000"}]},
        ]
    """
    if sensors is None:
        raise RuntimeError("please config sensors")

    for s in sensors:
        values = s["tmpvalues"]
        for val in values:
            tmp = f'{s["path"]}/name'
            out = lnx.exec0("cat", tmp)
            if s["name"] not in out:
                raise RuntimeError(
                    f'wrong name {s["name"]} for {s["path"]} temp sensor. Out: {out}'
                )
            tmp = f'{s["path"]}/{val["valname"]}'
            out = lnx.exec0("cat", tmp)
            tempval = int(out.strip(""))
            if tempval > int(val["max"]):
                raise RuntimeError(
                    f'temp values {tempval} > allowed value {val["max"]}'
                )
            if tempval < int(val["min"]):
                raise RuntimeError(
                    f'temp values {tempval} < allowed value {val["min"]}'
                )
