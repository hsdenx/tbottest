#
# collection of testcases, which may can go into mainline
#
import typing
import tbot
import time
from tbot.machine import linux
from tbot.machine import board
from tbot.context import Optional
import re
import contextlib


def escape_ansi(line: str) -> str:
    """
    helper for escaping ansi codes

    :param line: string which should be escaped
    :return: ansi escaped string
    """
    # or re.compile(r'\x1b[^m]*m') ?
    ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")
    return ansi_escape.sub("", line)


def lnx_create_random(lnx: linux.LinuxShell, f: str, len: int,) -> bool:
    """
    create file f with len bytes and random content

    :param lnx: linux machine on which the file gets created
    :param f: full path and filename which gets reated
    :param len: length of created file
    """
    lnx.exec0("dd", "if=/dev/urandom", f"of={f}", "bs=1", f"count={len}")
    return True


def lnx_compare_files(
    lnx: linux.LinuxShell, f1: str, o1: int, f2: str, o2: int, length: int,
) -> bool:
    """
    compare the content of the 2 files f1 @ offset o1 and f2 @ o2
    raise RuntimeError if they differ.

    :param lnx: linux machine on which the files get compared
    :param f1: full path to first file
    :param o1: offset in first file
    :param f2: full path to second file
    :param o2: offset in first file
    :param length: length (in bytes)
    """
    option = "--skip"
    # busybox
    option = "-s"
    out1 = lnx.exec0(
        "hexdump", "-e", '"%03.2x"', option, str(o1), "-n", str(length), f1
    )
    out2 = lnx.exec0(
        "hexdump", "-e", '"%03.2x"', option, str(o2), "-n", str(length), f2
    )
    if out1 != out2:
        tbot.log.message(
            tbot.log.c(f"content differ:\n{f1}:\n{out1}\n{f2}\n{out2}").red
        )
        raise RuntimeError("files have not same content")
    return True

@tbot.testcase
def lnx_get_hwaddr(lnx: linux.LinuxShell, name: str) -> str:
    """
    get MAC address from interface output

    ToDo: add a cache if often called

    :param lnx: linux machine from which we want to get the hwaddr
    :param name: name of the interface
    """
    out = lnx.exec0("ifconfig", name)
    for line in out.split("\n"):
        if "HWaddr" in line:
            match = re.match(
                    r".*HWaddr (?P<hwaddr>[0-9a-fA-F]+:[0-9a-fA-F]+:[0-9a-fA-F]+:[0-9a-fA-F]+:[0-9a-fA-F]+:[0-9a-fA-F]+)",  # noqa: E501
                line,
            )
            if match is None:
                continue
            return match.group("hwaddr")

    raise RuntimeError(f"Could not get hwaddr for device {name}")


@tbot.testcase
def lnx_get_ipaddr(lnx: linux.LinuxShell, name: str, ip6: bool = False) -> str:
    """
    get ipaddr from ifconfig output

    ToDo: add a cache if often called

    :param lnx: linux machine from which we want to get the ipaddr
    :param name: name of the interface
    :param ip6: set to true if you want the ipv6 addr
    """
    out = lnx.exec0("ifconfig", name)
    for line in out.split("\n"):
        if ip6:
            if "inet6" in line:
                match = re.match(
                    r"\s+inet6\s+addr:(?P<ipaddr>\d+.\d+.\d+.\d+)\s+",  # noqa: E501
                    line,
                )
                if match is None:
                    match = re.match(
                        r"\s+inet6\s(?P<ipaddr>\d+.\d+.\d+.\d+)\s+",  # noqa: E501
                        line,
                    )

                if match is None:
                    continue
                return match.group("ipaddr")
        else:
            if "inet6" in line:
                continue
            if "inet" in line:
                match = re.match(
                    r"\s+inet\s+addr:(?P<ipaddr>\d+.\d+.\d+.\d+)\s+",  # noqa: E501
                    line,
                )
                if match is None:
                    match = re.match(
                        r"\s+inet\s(?P<ipaddr>\d+.\d+.\d+.\d+)\s+",  # noqa: E501
                        line,
                    )

                if match is None:
                    continue
                return match.group("ipaddr")

    raise RuntimeError(f"Could not get ip for device {name}")


@tbot.testcase
def linux_test_uname(
    lab: Optional[linux.LinuxShell] = None, lnx: Optional[linux.LinuxShell] = None,
) -> None:
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        lab.exec0("uname", "-a")
        lnx.exec0("uname", "-a")


def lnx_wait_for_ip(
    lnx: linux.LinuxShell,
    name: str,
    loops: int,
    timeout: int,
    ip6: bool = False,
) -> str:  # noqa: D107
    """
    wait until ip is set on device name

    :param lnx: linux machine we run
    :param name: name of the device for which we wait for the ip
    :param ip6: set to True if you want to get ipv6 ipaddr
    :param loops: maximal wait loops
    :param timeout: timeout if process is not found
    :return: ip addr
    """
    found = False
    loop = 0
    while (found == False):
        try:
            ret = lnx_get_ipaddr(lnx, name, ip6)
            return ret
        except:
            break
        loop += 1
        if loop > loops:
            break

        time.sleep(timeout)

    if found == False:
        raise RuntimeError(f"ip on device {name} not found")


def lnx_wait_for_file(
    lnx: linux.LinuxShell,
    name: str,
    loops: int,
    timeout: int
) -> bool:  # noqa: D107
    """
    wait until file with name name is found with "ls -l"

    :param lnx: linux machine we run
    :param name: name of the file for which we wait
    :param loops: maximal wait loops
    :param timeout: timeout if file is not found
    """
    found = False
    loop = 0
    while (found == False):
        ret, log = lnx.exec("ls", "-l", name)
        if ret == 0:
            return True

        loop += 1
        if loop > loops:
            break

        time.sleep(timeout)

    if found == False:
        raise RuntimeError(f"file {name} not found")


def lnx_wait_for_module(
    lnx: linux.LinuxShell,
    name: str,
    loops: int,
    timeout: int
) -> bool:  # noqa: D107
    """
    wait until module with name is loaded

    :param lnx: linux machine we run
    :param name: name of the module for which we wait
    :param loops: maximal wait loops
    :param timeout: timeout if modulename is not found
    """
    found = False
    loop = 0
    while (found == False):
        log = lnx.exec0("lsmod")
        for l in log.split("\n"):
            if name in l:
                return True

        loop += 1
        if loop > loops:
            break

        time.sleep(timeout)

    if found == False:
        raise RuntimeError(f"module {name} not loaded")


def lnx_wait_for_process(
    lnx: linux.LinuxShell,
    name: str,
    loops: int,
    timeout: int
) -> bool:  # noqa: D107
    """
    wait until process with name name is found with pidof

    :param lnx: linux machine we run
    :param name: name of the process for which we wait
    :param loops: maximal wait loops
    :param timeout: timeout if process is not found
    """
    found = False
    loop = 0
    while (found == False):
        ret, log = lnx.exec("pidof", name)
        if ret == 0:
            return True

        loop += 1
        if loop > loops:
            break

        time.sleep(timeout)

    if found == False:
        raise RuntimeError(f"process {name} not found")


@tbot.testcase
def board_ub_delete_env(
    ub: Optional[board.UBootShell] = None, mtdparts=["env", "env-red"],
) -> None:
    """
    erase the SPI Environment sectors in U-Boot

    :param ub: U-Boot machine we run on
    :param mtdparts: List of MTD parts we want to delete
    """
    with tbot.ctx() as cx:
        if ub is None:
            ub = cx.request(tbot.role.BoardUBoot)

        ub.exec0("sf", "probe")
        for p in mtdparts:
            ub.exec0("sf", "erase", p["name"], p["size"])


@tbot.testcase
def board_ub_delete_emmc(
    ub: Optional[board.UBootShell] = None, device: str = None, erasesz: str = None,
) -> None:
    """
    delete the emmc device

    :param ub: U-Boot machine we run on
    :param device: U-Boots dev number for the mmc
    :param erasesz: number of blocks which get erased (started from offset 0)
    """

    if device is None:
        raise RuntimeError("please configure device")
    if erasesz is None:
        raise RuntimeError(f"please configure erasesize for device {device}")

    with tbot.ctx() as cx:
        if ub is None:
            ub = cx.request(tbot.role.BoardUBoot)

        ub.exec0("echo", "delete_emmc")
        ub.exec0("mmc", "dev", device)
        ub.exec0("mmc", "info")
        ub.exec0("mmc", "erase", "0", erasesz)


def board_wait_for_device(
    lnx: Optional[linux.LinuxShell] = None,
    device: str = None,
    retries: int = 1,
    retry_timeout: float = 0.1,
) -> None:
    """
    wait for device until it is up

    :param lnx: linux machine we work on
    :param device: path to device we wait for
    :param retries: retry count
    :param retry_timeout: float, sleep after device is not up
    """
    if device is None:
        raise RuntimeError("please configure device")

    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

    i = 0
    while 1 < retries:
        # fix me how to use
        # http://tbot.tools/modules/machine_linux.html?highlight=background#tbot.machine.linux.RedirBoth
        rcode, log = lnx.exec(linux.Raw(f"ls -al {device} &> /dev/null"))
        if rcode == 0:
            # also wait timeoutafter we detect the device, as at least
            # on raspberry pi, device is not always writeable after
            # device appears
            time.sleep(retry_timeout)
            return

        time.sleep(retry_timeout)
        i += 1

    raise RuntimeError("Device {device} does not come up")


@tbot.testcase
def board_set_default(
    lab: Optional[linux.LinuxShell] = None,
    ub: Optional[board.UBootShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
    mtdparts=["env", "env-red"],
    device: str = None,
    erasesz: str = None,
) -> None:
    """
    set board into default state, so we have a clean base
    for all our tests.

    - delete SPI NOR
    - delete emmc

    :param lab: lab linux machine
    :param ub: U-Boot machine we run on
    :param lnx: board linux machine
    :param mtdparts: List of MTD parts we want to delete
    :param device: U-Boots dev number for the mmc
    :param erasesz: number of blocks which get erased (started from offset 0)
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        if ub is None:
            ub = cx.request(tbot.role.BoardUBoot)

        board_ub_delete_env(ub, mtdparts)
        board_ub_delete_emmc(ub, device, erasesz)


def lab_check_part_exists_and_create(
    lab: Optional[linux.LinuxShell] = None, device: str = None, partition: str = None,
) -> None:
    """
    check if partition exists on device.

    ToDo: create it if not

    :param lab: linux machine we work on
    :param device: device on which the partition must exist
    :param partition: partition name

    """
    if device is None:
        raise RuntimeError("please configure device")
    if partition is None:
        raise RuntimeError(f"please configure partition for device {device}")

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        rcode, log = lab.exec("sudo", "fdisk", "-l", device)
        if rcode == 0:
            return

        raise RuntimeError("Create partition on {device} not implemented")


def board_prepare_tmpmnt(
    lab: Optional[linux.LinuxShell] = None,
    device: str = None,
    partition: str = None,
    retries: int = 1,
    retry_timeout: float = 0.1,
):
    if device is None:
        raise RuntimeError("please configure device")
    if partition is None:
        raise RuntimeError(f"please configure partition for device {device}")

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        # do not wait for automount
        # if your OS automounts the sd card
        # disable with
        # $ cat /etc/udev/rules.d/80-udisks2-nosdcard.rules
        # # do not automount sd card
        # SUBSYSTEMS=="usb", ENV{UDISKS_IGNORE}="1"
        #
        # and execute "systemctl restart udisks2.service"

        # wait for device
        board_wait_for_device(lab, f"{device}1", retries, retry_timeout)

        tmpdev = f"{device}{partition}"

        # check if tmp is mounted, if so unmount it
        tmppath = lab.tmpmntdir(tmpdev)._local_str()
        rcode, log = lab.exec("mount", linux.Pipe, "grep", tmppath)
        if rcode == 0:
            lab.exec0("sudo", "umount", tmppath)
        else:
            lab.exec0("mkdir", "-p", tmppath)
            # check if part exists, if not create it
            lab_check_part_exists_and_create(lab, device, partition)

        # mount tmpdir
        lab.exec0("sudo", "mount", tmpdev, tmppath)

        return tmppath


def board_lx_getbootcounter(lnx: Optional[linux.LinuxShell] = None,) -> str:
    val = lnx.exec0("bootcount", "/sys/bus/nvmem/devices/rv3028_nvram0/nvmem", "read")
    tbot.log.message(tbot.log.c(f"bootcount linux {val}").green)
    return val


@tbot.testcase
def board_ub_bootcounter(
    lab: typing.Optional[linux.LinuxShell] = None,
    board: typing.Optional[board.Board] = None,
    ubx: typing.Optional[board.UBootShell] = None,
) -> None:
    with lab or tbot.acquire_lab() as lh:
        with contextlib.ExitStack() as bx:
            with contextlib.ExitStack() as cx:
                b = cx.enter_context(tbot.acquire_board(lh))
                ub = cx.enter_context(tbot.acquire_uboot(b))

                bval = 1
                ret = ub.env("bootcount")
                blimit = ub.env("bootlimit")
                if ret != str(bval):
                    raise RuntimeError(f"bootcount not 1 after power on {ret}")
                tbot.log.message(
                    tbot.log.c(f"bootcount {ret} after power on -> OK").green
                )

            # power off the board
            b = bx.enter_context(tbot.acquire_board(lh))
            while bval < int(blimit) + 2:
                # do bval < int(blimit) + 2 resets
                with contextlib.ExitStack() as cx:
                    ub = cx.enter_context(tbot.acquire_uboot(b))
                    ret = ub.env("bootcount")
                    if ret != str(bval):
                        raise RuntimeError(
                            f"bootcount not {bval} after soft reset {ret}"
                        )
                    if bval <= int(blimit):
                        if "Warning: Bootlimit" in ub.bootlog:
                            raise RuntimeError(
                                f"bootlimit notreached, but U-Boot uses altbootcmd!\n {ub.bootlog}"
                            )
                    else:
                        if "Warning: Bootlimit" not in ub.bootlog:
                            raise RuntimeError(
                                f"bootlimit reached, but U-Boot uses not altbootcmd!\n {ub.bootlog}"
                            )

                    tbot.log.message(
                        tbot.log.c(
                            f"test bootcount bval {bval} blimit {blimit} Ok"
                        ).green
                    )
                    bval += 1
                    ub.ch.sendline("res")

        tbot.log.message(tbot.log.c("Now power off / on and test bootcounter.").green)

        with contextlib.ExitStack() as bx:
            b = bx.enter_context(tbot.acquire_board(lh))
            ub = bx.enter_context(tbot.acquire_uboot(b))

            bval = 1
            ret = ub.env("bootcount")
            blimit = ub.env("bootlimit")
            if ret != str(bval):
                raise RuntimeError(f"bootcount not 1 after power on {ret}")

            tbot.log.message(tbot.log.c(f"bootcount {ret} after power on -> OK").green)
            if "Warning: Bootlimit" in ub.bootlog:
                raise RuntimeError(
                    f"bootlimit notreached, but U-Boot uses altbootcmd!\n {ub.bootlog}"
                )


# test bootcounter with linux
@tbot.testcase
def board_bootcounter_with_linux(
    lab: typing.Optional[linux.LinuxShell] = None,
    board: typing.Optional[board.Board] = None,
    ubx: typing.Optional[board.UBootShell] = None,
) -> None:
    with lab or tbot.acquire_lab() as lh:
        with contextlib.ExitStack() as bx:
            b = bx.enter_context(tbot.acquire_board(lh))
            with contextlib.ExitStack() as cx:
                ub = cx.enter_context(tbot.acquire_uboot(b))

                ubval = ub.env("bootcount")
                tbot.log.message(tbot.log.c(f"bootcount {ubval}").green)

                lnx = cx.enter_context(tbot.acquire_linux(ub))

                val = board_lx_getbootcounter(lnx)
                tbot.log.message(tbot.log.c(f"bootcount linux {val}").green)
                print(f"----- UB VAL {ubval} LX {val}")

                lnx.ch.sendline("reboot")

            with contextlib.ExitStack() as cx:
                ub = cx.enter_context(tbot.acquire_uboot(b))

                print(f"----- UB VAL {ubval} LX {val}")
                ubval = ub.env("bootcount")
                print(f"----- END UB VAL {ubval} LX {val}")


# get bootcounter in u-boot
# boot into linux
# check if same
# set bootcounter in linux
# boot into ub
# check if Ok


@tbot.testcase
def lnx_check_beeper(lnx: Optional[linux.LinuxShell] = None, beeper=None,) -> None:
    """
    check if dmesg output contains strings in dmesg_list

    :param lnx: linux machine on which beeper command is executed
    :param beeper: list of dictionwry with infos for beeper

    beeper definition example:

    .. code-block:: python

        beep = [
            {"freq":"440", "length":"1000", "device", "/dev/input/by-path/platform-buzzer-event"},
        ]
    """
    if beeper is None:
        raise RuntimeError("please configure beeper")

    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        for b in beeper:
            lnx.exec0("beep", "-f", b["freq"], "-l", b["length"], "-e", b["device"])


@tbot.testcase
def lnx_check_dmesg(
    lnx: Optional[linux.LinuxShell] = None,
    dmesg_strings=None,
    dmesg_false_strings=None,
) -> bool:
    """
    check if dmesg output contains strings in dmesg_list

    :param lnx: linux machine on which dmesg command is executed
    :param list dmesg_strings: list of strings which must be in dmesg
    :param list dmesg_false_strings: list of strings which sould not occur in dmesg
    """
    ret = True
    if dmesg_strings is not None:
        for s in dmesg_strings:
            r, out = lnx.exec("dmesg", linux.Pipe, "grep", s)
            if r:
                msg = f"String {s} not in dmesg output."
                tbot.log.message(tbot.log.c(msg).red)
                ret = False

    if dmesg_false_strings is not None:
        for s in dmesg_false_strings:
            r, out = lnx.exec("dmesg", linux.Pipe, "grep", s)
            if r == 0:
                msg = f"String {s} in dmesg output. Not allowed"
                tbot.log.message(tbot.log.c(msg).red)
                ret = False

    return ret


def common_install_debian(lnx: linux.LinuxShell, package,) -> bool:
    # may convert package into real package name on OS
    lnx.exec0("sudo", "apt-get", "-y", "install", package)
    return True


def common_install_fedora(lnx: linux.LinuxShell, package,) -> bool:
    # may convert package into real package name on OS
    lnx.exec0("sudo", "dnf", "-y", "install", package)
    return True


def lnx_install_package(lnx: linux.LinuxShell, package: str,) -> bool:
    """
    detect OS version installed on linux machine
    and try to install package

    :param lnx: linux machine on which the package is installed
    :param package: Name of the package
    """
    os = lnx.exec0("cat", "/etc/os-release")

    if "debian" in os:
        return common_install_debian(lnx, package)
    elif "Fedora" in os:
        return common_install_debian(lnx, package)
    else:
        raise RuntimeError(f"OS {os} not supported yet for automated installation")


def tbot_copy_file_to_board(
    lab: linux.LinuxShell, lnx: linux.LinuxShell, ethdevice: str, filename: str,
) -> None:
    """
    copy file filename from lab host in tmpdir
    to board on tmpdir

    :param lab: lab machine where the file can be found
    :param lnx: linux machine to which the file gets copied
    :param ethdevice: ethernet device which is used
    :param filename: name of the file

    """
    ethdev = lab.ethdevices[ini.generic_get_boardname()][ethdevice]
    ip = ethdev["ipaddr"]
    user = "root"
    # logfile path on lab
    src = lab.tmpdir() / filename
    srclocal = src._local_str()

    # logfile path on board
    bp = lnx.tmpdir() / filename
    bplocal = bp._local_str()

    # copy log from lab to board
    lab.exec0(
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        srclocal,
        f"{user}@{ip}:{bplocal}",
    )


def tbot_start_script_on_board(
    lab: linux.LinuxShell, lnx: linux.LinuxShell, ethdevice: str, scriptname: str,
):
    """
    copy script scriptname from lab host in tftp dir
    to board on tmpdir and execute it

    :param lab: lab machine where the script can be found
    :param lnx: linux machine to which the script gets copied
    :param ethdevice: ethernet device which is used
    :param scriptname: name of the script
    """
    ethdev = lab.ethdevices[ini.generic_get_boardname()][ethdevice]
    ip = ethdev["ipaddr"]
    user = "root"
    # logfile path on lab
    src = lab.tftp_dir() / scriptname
    srclocal = src._local_str()

    # logfile path on board
    bp = lnx.tmpdir() / scriptname
    bplocal = bp._local_str()

    # copy log from lab to board
    lab.exec0(
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        srclocal,
        f"{user}@{ip}:{bplocal}",
    )
    ret, out = lnx.exec(bplocal)

    return ret, out


def tbot_start_script_on_lab(
    lab: linux.LinuxShell,
    lnx: linux.LinuxShell,
    ethdevice: str,
    logfilename: str,
    scriptname: str,
    labtbottestcasepath: str,
):
    """
    copy an log file to labhost and start script scriptname, which should
    check, if logfile is Ok.

    :param lab: lab machine where the script can be found
    :param lnx: linux machine to which the script gets copied
    :param ethdevice: ethernet device which is used
    :param logfilename: logfilename
    :param scriptname: name of the script
    :param labtbottestcasepath: path where the script can be found on lab
    """
    ethdev = lab.ethdevices[ini.generic_get_boardname()][ethdevice]
    ip = ethdev["ipaddr"]
    user = "root"
    # logfile path on lab
    tmp = lab.tmpdir()
    labtmppath = tmp / logfilename
    lfp = labtmppath._local_str()
    scrpath = labtmppath = tmp / scriptname
    scrp = scrpath._local_str()

    # logfile path on board
    tmp = lnx.tmpdir()
    boardtmppath = tmp / logfilename
    bfp = boardtmppath._local_str()

    # copy log to lab
    lab.exec0(
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        f"{user}@{ip}:{bfp}",
        lfp,
    )
    # check if script is on lab
    with tbot.ctx() as cx:
        host = cx.request(tbot.role.LocalHost)
        copy = False
        ret, out = lab.exec("ls", "-1", scrp)
        if ret != 0:
            if labtbottestcasepath is None:
                raise RuntimeError(
                    f"could not install {scriptname}, please set labtbottestcasepath"
                )
            else:
                # if not try to copy
                copy = True
        else:
            # check md5sum, if different copy
            sumorg = host.exec0(
                "md5sum",
                f"{labtbottestcasepath}/{scriptname}",
                linux.Pipe,
                "cut",
                "-d",
                linux.Raw('" "'),
                "-f",
                linux.Raw('"1"'),
            )
            sumlab = lab.exec0(
                "md5sum",
                scrp,
                linux.Pipe,
                "cut",
                "-d",
                linux.Raw('" "'),
                "-f",
                linux.Raw('"1"'),
            )
            if sumorg != sumlab:
                copy = True

        if copy:
            host.exec0(
                "scp",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                f"{labtbottestcasepath}/{scriptname}",
                f"{lab.username}@{lab.hostname}:{scrp}",
            )

    ret, out = lab.exec(scrp, "-i", lfp)
    if ret != 0:
        lnx.interactive()

    return ret, out

THREADS = {}
import uuid

def tbot_start_thread(
    lnx: linux.LinuxShell = None,
    cmd: str = None,
) -> uuid.UUID:  # noqa: D107
    """
    start linux command in thread and return an id

    output of the command gets stored in

    .. code-block::

        stdout : f"/tmp/thread_1_{tid}"
        stderr : f"/tmp/thread_2_{tid}"

    :param lnx: linux machine where the command **cmd** is started in background
    :param cmd: command which gets started in background
    :return: uuid.UUID id
    """
    tid = uuid.uuid4()

    logfile_stdout = f"/tmp/thread_1_{tid}"
    logfile_stderr = f"/tmp/thread_2_{tid}"
    lnx.exec(linux.Raw(f"{cmd} 2>{logfile_stderr} 1>{logfile_stdout} &"))
    pid = lnx.env("!")

    newt = {"lnx":lnx, "pid":pid, "cmd":cmd, "stdout":logfile_stdout, "stderr":logfile_stderr}
    try:
        tmpdict = THREADS[tid]
    except:
        RuntimeError(f"threadid {tid} already in use")

    THREADS[tid] = newt

    return tid

def tbot_stop_thread(
    tid: uuid.UUID = None,
    signal: str = None,
) -> int:  # noqa: D107
    """
    stop linux command with tid

    :param lnx: linux machine where the command **cmd** is started in background
    :param tid: id got from tbot_start_thread
    :param signal: may you need to kill the process with an special signal number
    """
    tmp = THREADS[tid]
    lnx = tmp["lnx"]
    pid = tmp["pid"]
    sig = ""
    if signal != None:
        lnx.exec("kill", signal, pid, linux.Then, "wait", pid)
    else:
        lnx.exec("kill", pid, linux.Then, "wait", pid)

    return THREADS.pop(tid)


