import tbot
from tbot.machine import linux

from tbottest.tc.common import lnx_create_random
from tbottest.tc.common import lnx_compare_files


def _write_random_and_verify(lnx: linux.LinuxShell, tmpf: str, dev: str, t: dict) -> None:
    lnx_create_random(lnx, tmpf, int(t["cnt"]) * int(t["bs"]))
    lnx.exec0(
        "dd",
        f"if={tmpf}",
        f"of={dev}",
        f"bs={t['bs']}",
        f"count={t['cnt']}",
        f"seek={t['seek']}",
    )
    try:
        lnx_compare_files(
            lnx,
            tmpf,
            0,
            dev,
            int(t["seek"]) * int(t["bs"]),
            int(t["cnt"]) * int(t["bs"]),
        )
    except Exception:
        lnx.interactive()


def _hexdump(lnx: linux.LinuxShell, path: str, skipflag: str, length: int) -> str:
    return lnx.exec0("hexdump", "-e", '"%03.2x"', skipflag, "0", "-n", str(length), path)


def lnx_mtd_nvram(
    lnx: linux.LinuxShell,
    dev: str = "/dev/mtd0",
    tests=None,
) -> None:
    """
    write and reread random data on device dev
    offsets, bytesize and length is defined in
    array tests which contain dictionary of form

    .. code-block:: python

        {"bs" : "1", "cnt" : "2", "seek" : "0"}

    example:

    .. code-block:: python

        tests = [
            {"bs" : "1", "cnt" : "2", "seek" : "0"},
            {"bs" : "1", "cnt" : "2", "seek" : "5"},
            {"bs" : "1", "cnt" : "20", "seek" : "5"},
            {"bs" : "1", "cnt" : "26", "seek" : "0"},
        ]

    """
    if tests is None:
        raise RuntimeError("please define tests")

    tmpf = "/tmp/gnlmpf"

    lnx.exec0("date", linux.Raw(">"), tmpf)
    lnx.exec0("cat", tmpf)
    for t in tests:
        _write_random_and_verify(lnx, tmpf, dev, t)


@tbot.testcase
def lnx_mtd_nvram_reboot(
    dev: str = "/dev/mtd0",
    tests=None,
) -> None:
    """
    prerequisite: Board boots into linux

    fill device with random data, as defined in tests an
    reboot and check if the nvram contains the same data
    after the reboot.

    .. code-block:: python

        {"bs" : "1", "cnt" : "2", "seek" : "0"}

    example:

    .. code-block:: python

        tests = [
            {"bs" : "1", "cnt" : "2", "seek" : "0"},
            {"bs" : "1", "cnt" : "2", "seek" : "5"},
            {"bs" : "1", "cnt" : "20", "seek" : "5"},
            {"bs" : "1", "cnt" : "26", "seek" : "0"},
        ]
    """
    if tests is None:
        raise RuntimeError("please define tests")

    tmpf = "/tmp/gnlmpf"

    # -s is the skip-offset flag for both busybox and non-busybox hexdump
    option = "-s"
    for t in tests:
        length = int(t["cnt"]) * int(t["bs"])

        with tbot.ctx.request(tbot.role.BoardLinux) as lnx:
            _write_random_and_verify(lnx, tmpf, dev, t)
            out = _hexdump(lnx, tmpf, option, length)

        with tbot.ctx.request(tbot.role.BoardLinux, reset=True) as lnx:
            lnx.exec0(
                "dd",
                f"if={dev}",
                f"of={tmpf}",
                f"bs={t['bs']}",
                f"count={t['cnt']}",
                f"skip={t['seek']}",
            )
            outn = _hexdump(lnx, tmpf, option, length)

        if out != outn:
            tbot.log.message(
                tbot.log.c(f"content differ:\noriginal:\n{out}\nnew\n{outn}").red
            )
            raise RuntimeError("files have not same content")
