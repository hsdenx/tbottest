import tbot
import time
from tbot.machine import linux
from tbot.context import Optional

from tbottest.tc.common import lnx_create_random
from tbottest.tc.common import tbot_copy_file_to_board


def board_lnx_rs485(
    lab: Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
    ethdevice=None,
    rs485labdev=None,
    rs485baud=None,
    rs485boarddev=None,
    rs485lengths=None,
    debug = 0,
):
    """
    prerequisite: Board boots into linux

    simple RS485 test, send and receive some random bytes

    :param lab: lab machine where we work on
    :param lnx: linux machine where we work on
    :param ethdevice: name of ethernetdevice on labhost used for copying files from board to lab
    :param rs485labdev: path to serial device on lab host for testing rs485
                /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0PI210-if00-port0
    :param rs485baud: baudrate used for testing
    :param rs485boarddev: list of paths to serial device(s) on board for rs485 test
                    ["/dev/ttymxc2"]
    :param rs485lengths: list of lengths used for the test

    example call

    .. code-block:: python

        board_lnx_rs485(
            lab,
            lnx,
            ethdevice="eth0",
            rs485labdev="/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0PI210-if00-port0",
            rs485baud="115200",
            rs485boarddev="['/dev/ttymxc2']"
            rs485lengths="['1", '100']"
        )
    """
    if ethdevice is None:
        raise RuntimeError("please configure ethdevice")
    if rs485labdev is None:
        raise RuntimeError("please configure rs485labdev")
    if rs485baud is None:
        raise RuntimeError("please configure rs485baud")
    if rs485boarddev is None:
        raise RuntimeError("please configure rs485boarddev")
    if rs485lengths is None:
        raise RuntimeError("please configure rs485lengths")

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        lab.exec0("export", f"SERIAL_DEV={rs485labdev}")
        lab.exec0(
            "stty",
            "-F",
            linux.Raw("$SERIAL_DEV"),
            rs485baud,
            "ignbrk",
            "ignpar",
            "-brkint",
            "-icrnl",
            "-imaxbel",
            "-opost",
            "-onlcr",
            "-isig",
            "-icanon",
            "-iexten",
            "-echo",
            "-echoe",
            "-echok",
            "-echoctl",
            "-echoke",
            "raw",
        )
        lab.exec0("stty", "-F", linux.Raw("$SERIAL_DEV"))

        for boarddev in rs485boarddev:
            lnx.exec0("export", f"SERIAL_DEV={boarddev}")
            lnx.exec0(
                "stty",
                "-F",
                linux.Raw("$SERIAL_DEV"),
                rs485baud,
                "ignbrk",
                "ignpar",
                "-brkint",
                "-icrnl",
                "-imaxbel",
                "-opost",
                "-onlcr",
                "-isig",
                "-icanon",
                "-iexten",
                "-echo",
                "-echoe",
                "-echok",
                "-echoctl",
                "-echoke",
                "raw",
            )

            lnx.exec0("stty", "-F", linux.Raw("$SERIAL_DEV"))

            sendfilebase = "rs485send"
            sendfilehexbase = sendfilebase + "hex"
            rcvfile = "rs485rcv"

            # send from lab to board
            src = lab
            tar = lnx
            sendfile = src.tmpdir() / sendfilebase
            sendfilehex = src.tmpdir() / sendfilehexbase
            rcvtmpfile = tar.tmpdir() / rcvfile

            tbot.log.message(tbot.log.c("Testing RS485 from lab to board").green)
            for length in rs485lengths:
                # enable receiver
                #time.sleep(5)
                tar.exec(
                    "cat",
                    linux.Raw("$SERIAL_DEV"),
                    linux.RedirStdout(rcvtmpfile),
                    linux.Raw("&"),
                )
                pid = tar.env("!")

                # create randomfile and send
                lnx_create_random(src, sendfile._local_str(), length)
                src.exec0(
                    "hexdump",
                    "-C",
                    sendfile._local_str(),
                    linux.Raw(">"),
                    sendfilehex._local_str(),
                )
                src.exec0(
                    "cat",
                    sendfilehex._local_str(),
                    linux.Raw(">"),
                    linux.Raw("$SERIAL_DEV"),
                )
                if debug:
                    src.exec0("cat", sendfilehex._local_str())

                #time.sleep(2)
                tar.exec("kill", pid, linux.Then, "wait", pid)
                if debug:
                    tar.exec0("cat", rcvtmpfile._local_str())

                # compare send and received file
                tbot_copy_file_to_board(lab, lnx, ethdevice, sendfilehexbase)
                try:
                    tar.exec0("cmp", tar.tmpdir() / sendfilehexbase, rcvtmpfile._local_str())
                except:
                    tar.exec0("cat", tar.tmpdir() / sendfilehexbase)
                    tar.exec0("cat", rcvtmpfile._local_str())
                    raise RuntimeError("RS485 receive error")

            tbot.log.message(tbot.log.c("Testing RS485 from board to lab").green)
            src = lnx
            tar = lab
            sendfile = src.tmpdir() / sendfilebase
            sendfilehex = src.tmpdir() / sendfilehexbase
            rcvtmpfile = tar.tmpdir() / rcvfile

            for length in rs485lengths:
                # enable receiver
                tar.exec(
                    "cat",
                    linux.Raw("$SERIAL_DEV"),
                    linux.RedirStdout(rcvtmpfile),
                    linux.Raw("&"),
                )
                pid = tar.env("!")

                # create randomfile and send
                lnx_create_random(src, sendfile._local_str(), length)
                src.exec0(
                    "hexdump",
                    "-C",
                    sendfile._local_str(),
                    linux.Raw(">"),
                    sendfilehex._local_str(),
                )
                src.exec0(
                    "cat",
                    sendfilehex._local_str(),
                    linux.Raw(">"),
                    linux.Raw("$SERIAL_DEV"),
                )
                if debug:
                    src.exec0("cat", sendfilehex._local_str())

                #time.sleep(2)
                tar.exec("kill", pid, linux.Then, "wait", pid)
                if debug:
                    tar.exec0("cat", rcvtmpfile._local_str())

                # compare send and received file
                tbot_copy_file_to_board(lab, lnx, ethdevice, rcvfile)
                try:
                    lnx.exec0("cmp", sendfilehex, lnx.tmpdir() / rcvfile)
                except:
                    src.exec0("cat", sendfilehex._local_str())
                    src.exec0("cat", lnx.tmpdir() / rcvfile)
                    raise RuntimeError("RS485 send error")
