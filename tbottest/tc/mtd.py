import re

import tbot
from tbot.machine import linux

import tbottest.initconfig as ini

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


def _proc_mtd(lnx: linux.LinuxShell) -> list:
    """
    Parse /proc/mtd into a list of (index, size in bytes, name).
    """
    parts = []
    for line in lnx.exec0("cat", "/proc/mtd").splitlines():
        m = re.match(r'^mtd(\d+):\s+([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+"([^"]*)"', line)
        if m:
            parts.append((int(m.group(1)), int(m.group(2), 16), m.group(3)))
    if not parts:
        raise RuntimeError("no MTD partitions found in /proc/mtd")
    return parts


@tbot.testcase
def lnx_mtd_dump(
    ethdevice: str = "eth0",
    subdir: str = "dump",
) -> None:
    """
    prerequisite: Board boots into linux, reachable with ssh as root

    Dump every MTD partition of the board into the lab host's tftp
    directory, below subdir, and verify each dump against the board.

    The board side only reads, through the /dev/mtdrN nodes, which the
    kernel opens read only. The data goes from the board to the lab host
    with ssh ("ssh root@<ipaddr> cat /dev/mtdrN"), straight into a file on
    the lab host. The lab host needs sshpass: the root password from
    linux_password is handed over with "sshpass -e" in the SSHPASS
    variable of a subshell, so it shows up neither in the command log nor
    in the process list. The board computes md5sum of every partition over
    its console, the lab host does the same on the files, and sizes and
    sums have to match.

    Files written: mtd<N>-<name>.bin per partition, proc-mtd.txt with the
    board's /proc/mtd, and md5sums.txt.
    """
    with tbot.ctx() as cx:
        lab = cx.request(tbot.role.LabHost)
        lnx = cx.request(tbot.role.BoardLinux)

        ip = lab.ethdevices[ini.generic_get_boardname()][ethdevice]["ipaddr"]
        password = lnx.password
        dumpdir = lab.tftp_dir() / subdir
        lab.exec0("mkdir", "-p", dumpdir)

        procmtd = lnx.exec0("cat", "/proc/mtd")
        (dumpdir / "proc-mtd.txt").write_text(procmtd)

        sums = []
        with lab.subshell():
            # Set directly on the channel, so it does not end up in the log.
            lab.ch.sendline("export SSHPASS=" + lab.escape(password))
            lab.ch.read_until_prompt()
            for idx, size, name in _proc_mtd(lnx):
                sums.append(_dump_one(lab, lnx, ip, dumpdir, idx, size, name))

        (dumpdir / "md5sums.txt").write_text("\n".join(sums) + "\n")


def _dump_one(lab, lnx, ip, dumpdir, idx: int, size: int, name: str) -> str:
    """
    Dump one MTD partition to the lab host and verify it. Needs SSHPASS
    set in the lab host's shell. Returns the md5sums.txt line.
    """
    dev = f"/dev/mtdr{idx}"
    fname = f"mtd{idx}-{name}.bin"
    dst = dumpdir / fname

    boardsum = lnx.exec0("md5sum", dev).split()[0]

    lab.exec0(
        "sshpass",
        "-e",
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        f"root@{ip}",
        f"cat {dev}",
        linux.RedirStdout(dst),
    )

    labsize = int(lab.exec0("stat", "-c", "%s", dst).strip())
    if labsize != size:
        raise RuntimeError(f"{fname}: {labsize} bytes, partition has {size}")

    labsum = lab.exec0("md5sum", dst).split()[0]
    if labsum != boardsum:
        raise RuntimeError(f"{fname}: md5sum {labsum}, board has {boardsum}")

    tbot.log.message(f"{fname}: {size} bytes, md5sum {labsum}, verified")
    return f"{labsum}  {fname}"
