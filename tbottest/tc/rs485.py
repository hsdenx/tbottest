import tbot
from tbot.machine import linux
from tbot.context import Optional

from tbottest.tc.common import lnx_create_random
from tbottest.tc.common import tbot_copy_file_to_board


def _configure_serial(host: linux.LinuxShell, dev: str, baud: str) -> None:
    host.exec0("export", f"SERIAL_DEV={dev}")
    host.exec0(
        "stty",
        "-F",
        linux.Raw("$SERIAL_DEV"),
        baud,
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
    host.exec0("stty", "-F", linux.Raw("$SERIAL_DEV"))


def _rs485_send_and_compare(
    lab: linux.LinuxShell,
    lnx: linux.LinuxShell,
    src: linux.LinuxShell,
    tar: linux.LinuxShell,
    ethdevice: str,
    length: str,
    debug: int,
    errmsg: str,
) -> None:
    sendfilebase = "rs485send"
    sendfilehexbase = sendfilebase + "hex"
    rcvfile = "rs485rcv"

    sendfile = src.tmpdir() / sendfilebase
    sendfilehex = src.tmpdir() / sendfilehexbase
    rcvtmpfile = tar.tmpdir() / rcvfile

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

    tar.exec("kill", pid, linux.Then, "wait", pid)
    if debug:
        tar.exec0("cat", rcvtmpfile._local_str())

    if src is lab:
        # lab -> board: the reference file lives on lab; copy it onto
        # the board (tbot_copy_file_to_board is lab->board only) and
        # compare there against what the board received
        tbot_copy_file_to_board(lab, lnx, ethdevice, sendfilehexbase)
        try:
            tar.exec0("cmp", tar.tmpdir() / sendfilehexbase, rcvtmpfile._local_str())
        except Exception:
            tar.exec0("cat", tar.tmpdir() / sendfilehexbase)
            tar.exec0("cat", rcvtmpfile._local_str())
            raise RuntimeError(errmsg)
    else:
        # board -> lab: the reference file already lives on the
        # board; copy the lab's received file onto the board too and
        # compare there
        tbot_copy_file_to_board(lab, lnx, ethdevice, rcvfile)
        try:
            lnx.exec0("cmp", sendfilehex, lnx.tmpdir() / rcvfile)
        except Exception:
            src.exec0("cat", sendfilehex._local_str())
            src.exec0("cat", lnx.tmpdir() / rcvfile)
            raise RuntimeError(errmsg)


def board_lnx_rs485(
    lab: Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
    ethdevice=None,
    rs485labdev=None,
    rs485baud=None,
    rs485boarddev=None,
    rs485lengths=None,
    debug=0,
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
            rs485boarddev=["/dev/ttymxc2"],
            rs485lengths=["1", "100"],
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

        _configure_serial(lab, rs485labdev, rs485baud)

        for boarddev in rs485boarddev:
            _configure_serial(lnx, boarddev, rs485baud)

            tbot.log.message(tbot.log.c("Testing RS485 from lab to board").green)
            for length in rs485lengths:
                _rs485_send_and_compare(
                    lab, lnx, lab, lnx, ethdevice, length, debug, "RS485 receive error"
                )

            tbot.log.message(tbot.log.c("Testing RS485 from board to lab").green)
            for length in rs485lengths:
                _rs485_send_and_compare(
                    lab, lnx, lnx, lab, ethdevice, length, debug, "RS485 send error"
                )
